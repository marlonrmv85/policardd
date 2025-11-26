from flask import Flask, render_template, request, flash, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField, TextAreaField, FloatField, PasswordField
from wtforms.validators import DataRequired, NumberRange, Email, Length, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import os
import re
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# VERIFICACIÓN DE BASE DE DATOS AL INICIO
print("🔍 VERIFICANDO CONFIGURACIÓN DE BD...")
database_url = os.environ.get('DATABASE_URL', 'sqlite:///policard.db')
print(f"📊 DATABASE_URL: {database_url}")

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
    print("✅ PostgreSQL URL corregida")

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'policard2025secret')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

print(f"🎯 URL FINAL: {app.config['SQLALCHEMY_DATABASE_URI']}")

db = SQLAlchemy(app)

# ==================== MODELOS ====================
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    activo = db.Column(db.Boolean, default=True)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    
    banco = db.relationship('Banco', backref='usuario', uselist=False, cascade='all, delete-orphan')

class Banco(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nombre_banco = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20))
    sitio_web = db.Column(db.String(200))
    descripcion = db.Column(db.Text)
    logo_url = db.Column(db.String(300))
    aprobado = db.Column(db.Boolean, default=False)
    fecha_aprobacion = db.Column(db.DateTime)
    
    tarjetas = db.relationship('Tarjeta', backref='banco_rel', cascade='all, delete-orphan')

class Tarjeta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    banco_id = db.Column(db.Integer, db.ForeignKey('banco.id'), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    cat = db.Column(db.Float, nullable=False)
    anualidad = db.Column(db.Float, nullable=False)
    edad_minima = db.Column(db.Integer, nullable=False)
    beneficios = db.Column(db.Text)
    imagen_url = db.Column(db.String(300))
    aprobada = db.Column(db.Boolean, default=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_aprobacion = db.Column(db.DateTime)
    
    @property
    def banco_nombre(self):
        return self.banco_rel.nombre_banco if self.banco_rel else 'N/A'

class Solicitud(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    banco_id = db.Column(db.Integer, db.ForeignKey('banco.id'), nullable=False)
    tipo_solicitud = db.Column(db.String(50), nullable=False)
    referencia_id = db.Column(db.Integer)
    estado = db.Column(db.String(20), default='pendiente')
    comentario_admin = db.Column(db.Text)
    fecha_solicitud = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_respuesta = db.Column(db.DateTime)
    
    banco = db.relationship('Banco', backref='solicitudes')

# ==================== FORMULARIOS ====================
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Contraseña', validators=[DataRequired()])

class RegistroBancoForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Contraseña', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirmar Contraseña', validators=[DataRequired(), EqualTo('password')])
    nombre_contacto = StringField('Nombre de Contacto', validators=[DataRequired()])
    nombre_banco = StringField('Nombre del Banco', validators=[DataRequired()])
    telefono = StringField('Teléfono', validators=[DataRequired()])
    sitio_web = StringField('Sitio Web')
    descripcion = TextAreaField('Descripción del Banco')

class TarjetaForm(FlaskForm):
    nombre = StringField('Nombre de la Tarjeta', validators=[DataRequired()])
    tipo = SelectField('Tipo', choices=[
        ('', 'Selecciona un tipo'),
        ('estudiante', 'Estudiante'), 
        ('joven', 'Joven'), 
        ('clasica', 'Clásica')
    ], validators=[DataRequired()])
    cat = FloatField('CAT (%)', validators=[DataRequired(), NumberRange(min=0)])
    anualidad = FloatField('Anualidad ($)', validators=[DataRequired(), NumberRange(min=0)])
    edad_minima = IntegerField('Edad Mínima', validators=[DataRequired(), NumberRange(min=18, max=100)])
    beneficios = TextAreaField('Beneficios')
    imagen_url = StringField('URL de la Imagen')

class BusquedaForm(FlaskForm):
    edad = IntegerField('Edad', validators=[DataRequired(), NumberRange(min=18, max=100)])
    tipo = SelectField('Tipo', choices=[
        ('', 'Selecciona un tipo'),
        ('estudiante', 'Estudiante'), 
        ('joven', 'Joven'), 
        ('clasica', 'Clásica')
    ], validators=[DataRequired()])

# ==================== DECORADORES ====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Debes iniciar sesión para acceder a esta página', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Debes iniciar sesión', 'warning')
            return redirect(url_for('login'))
        usuario = Usuario.query.get(session['user_id'])
        if not usuario or usuario.tipo != 'admin':
            flash('No tienes permisos de administrador', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def banco_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Debes iniciar sesión', 'warning')
            return redirect(url_for('login'))
        usuario = Usuario.query.get(session['user_id'])
        if not usuario or usuario.tipo != 'banco':
            flash('No tienes permisos de banco', 'danger')
            return redirect(url_for('index'))
        if not usuario.banco:
            flash('No se encontró información del banco', 'danger')
            return redirect(url_for('logout'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== RUTAS PÚBLICAS ====================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/tarjetas')
def tarjetas():
    try:
        todas_tarjetas = Tarjeta.query.filter_by(aprobada=True).all()
        return render_template('tarjetas.html', tarjetas=todas_tarjetas)
    except Exception as e:
        flash('Error al cargar las tarjetas', 'danger')
        return render_template('tarjetas.html', tarjetas=[])

@app.route('/buscar', methods=['GET', 'POST'])
def buscar():
    form = BusquedaForm()
    resultados = []
    
    if form.validate_on_submit():
        try:
            edad = form.edad.data
            tipo = form.tipo.data
            resultados = Tarjeta.query.filter(
                Tarjeta.edad_minima <= edad, 
                Tarjeta.tipo == tipo,
                Tarjeta.aprobada == True
            ).all()
            
            if resultados:
                flash(f'¡Encontramos {len(resultados)} tarjeta(s) para ti!', 'success')
            else:
                flash('No encontramos tarjetas. Intenta con otros filtros.', 'warning')
        except Exception as e:
            flash('Error al realizar la búsqueda', 'danger')
    
    return render_template('buscar.html', form=form, resultados=resultados)

@app.route('/educacion')
def educacion():
    return render_template('educacion.html')

@app.route('/calculadora')
def calculadora():
    return render_template('calculadora.html')

# ==================== RUTA TEMPORAL PARA RESET ====================
@app.route('/reset-db')
def reset_db_route():
    try:
        with app.app_context():
            print("🔄 Iniciando reset de base de datos...")
            db.drop_all()
            db.create_all()
            
            admin = Usuario(
                email='admin@policard.com',
                password=generate_password_hash('AdminPoliCard2025!'),
                nombre='Administrador PoliCard',
                tipo='admin'
            )
            db.session.add(admin)
            db.session.commit()
            
        return '''
        <!DOCTYPE html>
        <html>
        <head><script src="https://cdn.tailwindcss.com"></script></head>
        <body class="bg-gray-100 p-8">
            <div class="max-w-md mx-auto bg-white rounded-lg shadow-lg p-6 text-center">
                <div class="text-green-500 text-6xl mb-4">✅</div>
                <h1 class="text-2xl font-bold text-gray-800 mb-4">Base de Datos Reseteada</h1>
                <p class="text-gray-600 mb-6">Credenciales: admin@policard.com / AdminPoliCard2025!</p>
                <a href="/login" class="block w-full bg-green-600 text-white py-3 rounded-lg hover:bg-green-700 transition">
                    Iniciar Sesión
                </a>
            </div>
        </body>
        </html>
        '''
    except Exception as e:
        return f'<h1>❌ Error: {str(e)}</h1>'

# ==================== RUTA TEMPORAL PARA DATOS DE PRUEBA ====================
@app.route('/create-sample-data')
def create_sample_data():
    try:
        with app.app_context():
            # Crear banco de prueba
            banco = Banco.query.filter_by(nombre_banco='Banco de Prueba').first()
            if not banco:
                usuario_banco = Usuario(
                    email='banco@prueba.com',
                    password=generate_password_hash('banco123'),
                    nombre='Gerente Banco Prueba',
                    tipo='banco'
                )
                db.session.add(usuario_banco)
                db.session.flush()
                
                banco = Banco(
                    usuario_id=usuario_banco.id,
                    nombre_banco='Banco de Prueba',
                    telefono='555-1234',
                    aprobado=True
                )
                db.session.add(banco)
                db.session.flush()
            
            # Crear tarjetas de prueba
            tarjetas_ejemplo = [
                {
                    'nombre': 'Tarjeta Estudiante Plus',
                    'tipo': 'estudiante',
                    'cat': 25.5,
                    'anualidad': 0,
                    'edad_minima': 18,
                    'beneficios': 'Sin anualidad, cashback 2%'
                },
                {
                    'nombre': 'Tarjeta Joven Gold',
                    'tipo': 'joven', 
                    'cat': 28.0,
                    'anualidad': 300,
                    'edad_minima': 21,
                    'beneficios': 'Puntos canjeables, acceso a salas VIP'
                }
            ]
            
            for tarjeta_data in tarjetas_ejemplo:
                if not Tarjeta.query.filter_by(nombre=tarjeta_data['nombre']).first():
                    tarjeta = Tarjeta(
                        nombre=tarjeta_data['nombre'],
                        banco_id=banco.id,
                        tipo=tarjeta_data['tipo'],
                        cat=tarjeta_data['cat'],
                        anualidad=tarjeta_data['anualidad'],
                        edad_minima=tarjeta_data['edad_minima'],
                        beneficios=tarjeta_data['beneficios'],
                        aprobada=True
                    )
                    db.session.add(tarjeta)
            
            db.session.commit()
            
            return '''
            <!DOCTYPE html>
            <html>
            <head><script src="https://cdn.tailwindcss.com"></script></head>
            <body class="bg-gray-100 p-8">
                <div class="max-w-md mx-auto bg-white rounded-lg shadow-lg p-6 text-center">
                    <div class="text-green-500 text-6xl mb-4">✅</div>
                    <h1 class="text-2xl font-bold text-gray-800 mb-4">Datos de Prueba Creados</h1>
                    <div class="space-y-3">
                        <a href="/admin/tarjetas" class="block w-full bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700 transition">
                            Ver Tarjetas
                        </a>
                        <a href="/tarjetas" class="block w-full bg-green-600 text-white py-3 rounded-lg hover:bg-green-700 transition">
                            Ver Catálogo
                        </a>
                    </div>
                </div>
            </body>
            </html>
            '''
            
    except Exception as e:
        return f'<h1>❌ Error: {str(e)}</h1>'

# ==================== AUTENTICACIÓN ====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        try:
            usuario = Usuario.query.filter_by(email=form.email.data).first()
            if usuario and check_password_hash(usuario.password, form.password.data):
                session['user_id'] = usuario.id
                session['user_type'] = usuario.tipo
                session['user_name'] = usuario.nombre
                flash(f'¡Bienvenido {usuario.nombre}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Email o contraseña incorrectos', 'danger')
        except Exception as e:
            flash('Error al iniciar sesión', 'danger')
    
    return render_template('login.html', form=form)

@app.route('/registro-banco', methods=['GET', 'POST'])
def registro_banco():
    form = RegistroBancoForm()
    if form.validate_on_submit():
        try:
            if Usuario.query.filter_by(email=form.email.data).first():
                flash('Este email ya está registrado', 'danger')
                return redirect(url_for('registro_banco'))
            
            usuario = Usuario(
                email=form.email.data,
                password=generate_password_hash(form.password.data),
                nombre=form.nombre_contacto.data,
                tipo='banco'
            )
            db.session.add(usuario)
            db.session.flush()
            
            banco = Banco(
                usuario_id=usuario.id,
                nombre_banco=form.nombre_banco.data,
                telefono=form.telefono.data,
                sitio_web=form.sitio_web.data,
                descripcion=form.descripcion.data
            )
            db.session.add(banco)
            db.session.flush()
            
            solicitud = Solicitud(
                banco_id=banco.id,
                tipo_solicitud='banco',
                referencia_id=banco.id
            )
            db.session.add(solicitud)
            
            db.session.commit()
            flash('Registro exitoso. Pendiente de aprobación.', 'success')
            return redirect(url_for('login'))
        
        except Exception as e:
            db.session.rollback()
            flash('Error en el registro', 'danger')
    
    return render_template('registro_banco.html', form=form)

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada', 'info')
    return redirect(url_for('index'))

# ==================== DASHBOARD ====================
@app.route('/dashboard')
@login_required
def dashboard():
    usuario = Usuario.query.get(session['user_id'])
    if usuario.tipo == 'admin':
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('banco_dashboard'))

# ==================== PANEL ADMIN ====================
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    try:
        stats = {
            'total_bancos': Banco.query.count(),
            'bancos_pendientes': Banco.query.filter_by(aprobado=False).count(),
            'total_tarjetas': Tarjeta.query.count(),
            'tarjetas_pendientes': Tarjeta.query.filter_by(aprobada=False).count(),
            'solicitudes_pendientes': Solicitud.query.filter_by(estado='pendiente').count()
        }
        return render_template('admin/dashboard.html', stats=stats)
    except Exception as e:
        flash('Error al cargar el dashboard', 'danger')
        return redirect(url_for('index'))

@app.route('/admin/solicitudes')
@admin_required
def admin_solicitudes():
    try:
        solicitudes = Solicitud.query.filter_by(estado='pendiente').all()
        return render_template('admin/solicitudes.html', solicitudes=solicitudes)
    except Exception as e:
        return render_template('admin/solicitudes.html', solicitudes=[])

@app.route('/admin/solicitud/<int:id>/aprobar', methods=['POST'])
@admin_required
def aprobar_solicitud(id):
    try:
        solicitud = Solicitud.query.get_or_404(id)
        solicitud.estado = 'aprobada'
        solicitud.fecha_respuesta = datetime.utcnow()
        
        if solicitud.tipo_solicitud == 'banco':
            banco = Banco.query.get(solicitud.referencia_id)
            if banco:
                banco.aprobado = True
        elif solicitud.tipo_solicitud == 'tarjeta':
            tarjeta = Tarjeta.query.get(solicitud.referencia_id)
            if tarjeta:
                tarjeta.aprobada = True
        
        db.session.commit()
        flash('Solicitud aprobada', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al aprobar', 'danger')
    
    return redirect(url_for('admin_solicitudes'))

@app.route('/admin/tarjetas')
@admin_required
def admin_tarjetas():
    try:
        tarjetas = Tarjeta.query.all()
        return render_template('admin/tarjetas.html', tarjetas=tarjetas)
    except Exception as e:
        return render_template('admin/tarjetas.html', tarjetas=[])

# ==================== PANEL BANCO ====================
@app.route('/banco/dashboard')
@banco_required
def banco_dashboard():
    try:
        usuario = Usuario.query.get(session['user_id'])
        banco = usuario.banco
        
        stats = {
            'tarjetas_count': len(banco.tarjetas),
            'tarjetas_aprobadas': sum(1 for t in banco.tarjetas if t.aprobada),
            'solicitudes_pendientes': Solicitud.query.filter_by(banco_id=banco.id, estado='pendiente').count(),
            'banco_aprobado': banco.aprobado
        }
        
        return render_template('banco/dashboard.html', banco=banco, stats=stats)
    except Exception as e:
        flash('Error al cargar el dashboard', 'danger')
        return redirect(url_for('index'))

@app.route('/banco/tarjetas')
@banco_required
def banco_tarjetas():
    try:
        usuario = Usuario.query.get(session['user_id'])
        banco = usuario.banco
        tarjetas = banco.tarjetas
        return render_template('banco/tarjetas.html', tarjetas=tarjetas, banco=banco)
    except Exception as e:
        flash('Error al cargar tarjetas', 'danger')
        return redirect(url_for('banco_dashboard'))

# ==================== INICIALIZACIÓN ====================
def init_db():
    with app.app_context():
        try:
            db.create_all()
            if not Usuario.query.filter_by(email='admin@policard.com').first():
                admin = Usuario(
                    email='admin@policard.com',
                    password=generate_password_hash('AdminPoliCard2025!'),
                    nombre='Administrador',
                    tipo='admin'
                )
                db.session.add(admin)
                db.session.commit()
                print("✅ Base de datos inicializada")
        except Exception as e:
            print(f"❌ Error inicializando BD: {e}")

init_db()

# ==================== EJECUCIÓN ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)