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

# Configuración - usar variable de entorno en producción
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'policard2025secret')

# Configuración de base de datos para PostgreSQL en Render
def get_database_url():
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///policard.db')
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    return database_url

app.config['SQLALCHEMY_DATABASE_URI'] = get_database_url()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 300,
    'pool_pre_ping': True
}

db = SQLAlchemy(app)

# ==================== MODELOS ====================
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # 'admin' o 'banco'
    activo = db.Column(db.Boolean, default=True)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relación con banco (solo si es tipo banco)
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
    
    # Relación con tarjetas
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
        """Propiedad para compatibilidad con templates antiguos"""
        return self.banco_rel.nombre_banco if self.banco_rel else 'N/A'

class Solicitud(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    banco_id = db.Column(db.Integer, db.ForeignKey('banco.id'), nullable=False)
    tipo_solicitud = db.Column(db.String(50), nullable=False)  # 'banco' o 'tarjeta'
    referencia_id = db.Column(db.Integer)  # ID de banco o tarjeta
    estado = db.Column(db.String(20), default='pendiente')  # pendiente, aprobada, rechazada
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

# ==================== UTILIDADES ====================
def sanitizar_input(texto):
    """Sanitiza input para prevenir XSS básico"""
    if texto:
        return re.sub(r'<script.*?>.*?</script>', '', texto, flags=re.IGNORECASE)
    return texto

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
        # Verificar que el banco existe
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
        app.logger.error(f"Error en tarjetas: {e}")
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
                flash('No encontramos tarjetas que coincidan con tus criterios. Intenta con otros filtros.', 'warning')
        except Exception as e:
            app.logger.error(f"Error en buscar: {e}")
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
    """Ruta temporal para resetear la base de datos - ELIMINAR después de usar"""
    try:
        # Usar app_context explícitamente
        with app.app_context():
            print("🔄 Iniciando reset de base de datos...")
            
            # Eliminar todas las tablas
            db.drop_all()
            print("✅ Tablas eliminadas")
            
            # Crear todas las tablas
            db.create_all()
            print("✅ Tablas creadas")
            
            # Crear usuario admin
            admin = Usuario(
                email='admin@policard.com',
                password=generate_password_hash('AdminPoliCard2025!'),
                nombre='Administrador PoliCard',
                tipo='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Usuario admin creado")
            
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Base de Datos Reseteada</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-100 p-8">
            <div class="max-w-md mx-auto bg-white rounded-lg shadow-lg p-6 text-center">
                <div class="text-green-500 text-6xl mb-4">✅</div>
                <h1 class="text-2xl font-bold text-gray-800 mb-4">Base de Datos Reseteada</h1>
                <p class="text-gray-600 mb-6">La base de datos ha sido reinicializada correctamente.</p>
                
                <div class="bg-green-50 border border-green-200 rounded-lg p-4 mb-6">
                    <p class="font-semibold">Credenciales de Admin:</p>
                    <p>Email: <strong>admin@policard.com</strong></p>
                    <p>Contraseña: <strong>AdminPoliCard2025!</strong></p>
                </div>
                
                <div class="space-y-3">
                    <a href="/" class="block w-full bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700 transition">
                        Ir a la Página Principal
                    </a>
                    <a href="/login" class="block w-full bg-green-600 text-white py-3 rounded-lg hover:bg-green-700 transition">
                        Iniciar Sesión como Admin
                    </a>
                </div>
                
                <p class="text-sm text-gray-500 mt-6">
                    <strong>Recuerda eliminar esta ruta (/reset-db) después de usar.</strong>
                </p>
            </div>
        </body>
        </html>
        '''
    except Exception as e:
        return f'''
        <div class="max-w-md mx-auto bg-white rounded-lg shadow-lg p-6 text-center">
            <div class="text-red-500 text-6xl mb-4">❌</div>
            <h1 class="text-2xl font-bold text-gray-800 mb-4">Error al Resetear BD</h1>
            <p class="text-red-600 mb-4">Error: {str(e)}</p>
            <a href="/" class="inline-block bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition">
                Volver al Inicio
            </a>
        </div>
        '''

# ==================== AUTENTICACIÓN ====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        usuario = Usuario.query.get(session['user_id'])
        if usuario:
            return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        try:
            usuario = Usuario.query.filter_by(email=form.email.data).first()
            if usuario and check_password_hash(usuario.password, form.password.data):
                if not usuario.activo:
                    flash('Tu cuenta está desactivada. Contacta al administrador.', 'danger')
                    return redirect(url_for('login'))
                
                session['user_id'] = usuario.id
                session['user_type'] = usuario.tipo
                session['user_name'] = usuario.nombre
                flash(f'¡Bienvenido {usuario.nombre}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Email o contraseña incorrectos', 'danger')
        except Exception as e:
            app.logger.error(f"Error en login: {e}")
            flash('Error al iniciar sesión', 'danger')
    
    return render_template('login.html', form=form)

@app.route('/registro-banco', methods=['GET', 'POST'])
def registro_banco():
    form = RegistroBancoForm()
    if form.validate_on_submit():
        try:
            # Verificar si el email ya existe
            if Usuario.query.filter_by(email=form.email.data).first():
                flash('Este email ya está registrado', 'danger')
                return redirect(url_for('registro_banco'))
            
            # Crear usuario
            usuario = Usuario(
                email=sanitizar_input(form.email.data),
                password=generate_password_hash(form.password.data),
                nombre=sanitizar_input(form.nombre_contacto.data),
                tipo='banco'
            )
            db.session.add(usuario)
            db.session.flush()
            
            # Crear banco
            banco = Banco(
                usuario_id=usuario.id,
                nombre_banco=sanitizar_input(form.nombre_banco.data),
                telefono=sanitizar_input(form.telefono.data),
                sitio_web=sanitizar_input(form.sitio_web.data),
                descripcion=sanitizar_input(form.descripcion.data)
            )
            db.session.add(banco)
            db.session.flush()
            
            # Crear solicitud de aprobación
            solicitud = Solicitud(
                banco_id=banco.id,
                tipo_solicitud='banco',
                referencia_id=banco.id
            )
            db.session.add(solicitud)
            
            db.session.commit()
            flash('Registro exitoso. Tu solicitud está pendiente de aprobación.', 'success')
            return redirect(url_for('login'))
        
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error en registro_banco: {e}")
            flash('Error en el registro. Intenta nuevamente.', 'danger')
    
    return render_template('registro_banco.html', form=form)

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada exitosamente', 'info')
    return redirect(url_for('index'))

# ==================== DASHBOARD ====================
@app.route('/dashboard')
@login_required
def dashboard():
    try:
        usuario = Usuario.query.get(session['user_id'])
        if not usuario:
            session.clear()
            flash('Usuario no encontrado', 'danger')
            return redirect(url_for('login'))
            
        if usuario.tipo == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('banco_dashboard'))
    except Exception as e:
        app.logger.error(f"Error en dashboard: {e}")
        flash('Error al cargar el dashboard', 'danger')
        return redirect(url_for('index'))

# ==================== PANEL ADMIN ====================
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    try:
        total_bancos = Banco.query.count()
        bancos_pendientes = Banco.query.filter_by(aprobado=False).count()
        total_tarjetas = Tarjeta.query.count()
        tarjetas_pendientes = Tarjeta.query.filter_by(aprobada=False).count()
        solicitudes_pendientes = Solicitud.query.filter_by(estado='pendiente').count()
        
        stats = {
            'total_bancos': total_bancos,
            'bancos_pendientes': bancos_pendientes,
            'total_tarjetas': total_tarjetas,
            'tarjetas_pendientes': tarjetas_pendientes,
            'solicitudes_pendientes': solicitudes_pendientes
        }
        
        return render_template('admin/dashboard.html', stats=stats)
    except Exception as e:
        app.logger.error(f"Error en admin_dashboard: {e}")
        flash('Error al cargar el dashboard de administrador', 'danger')
        return redirect(url_for('index'))

@app.route('/admin/solicitudes')
@admin_required
def admin_solicitudes():
    try:
        solicitudes = Solicitud.query.filter_by(estado='pendiente').order_by(Solicitud.fecha_solicitud.desc()).all()
        return render_template('admin/solicitudes.html', solicitudes=solicitudes)
    except Exception as e:
        app.logger.error(f"Error en admin_solicitudes: {e}")
        flash('Error al cargar las solicitudes', 'danger')
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
                banco.fecha_aprobacion = datetime.utcnow()
        elif solicitud.tipo_solicitud == 'tarjeta':
            tarjeta = Tarjeta.query.get(solicitud.referencia_id)
            if tarjeta:
                tarjeta.aprobada = True
                tarjeta.fecha_aprobacion = datetime.utcnow()
        
        db.session.commit()
        flash('Solicitud aprobada exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error en aprobar_solicitud: {e}")
        flash('Error al aprobar la solicitud', 'danger')
    
    return redirect(url_for('admin_solicitudes'))

@app.route('/admin/solicitud/<int:id>/rechazar', methods=['POST'])
@admin_required
def rechazar_solicitud(id):
    try:
        solicitud = Solicitud.query.get_or_404(id)
        solicitud.estado = 'rechazada'
        solicitud.fecha_respuesta = datetime.utcnow()
        solicitud.comentario_admin = sanitizar_input(request.form.get('comentario', ''))
        
        db.session.commit()
        flash('Solicitud rechazada', 'info')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error en rechazar_solicitud: {e}")
        flash('Error al rechazar la solicitud', 'danger')
    
    return redirect(url_for('admin_solicitudes'))

@app.route('/admin/bancos')
@admin_required
def admin_bancos():
    try:
        bancos = Banco.query.all()
        return render_template('admin/bancos.html', bancos=bancos)
    except Exception as e:
        app.logger.error(f"Error en admin_bancos: {e}")
        flash('Error al cargar los bancos', 'danger')
        return render_template('admin/bancos.html', bancos=[])

@app.route('/admin/tarjetas')
@admin_required
def admin_tarjetas():
    try:
        tarjetas = Tarjeta.query.join(Banco).all()
        return render_template('admin/tarjetas.html', tarjetas=tarjetas)
    except Exception as e:
        app.logger.error(f"Error en admin_tarjetas: {e}")
        flash('Error al cargar las tarjetas', 'danger')
        return render_template('admin/tarjetas.html', tarjetas=[])

# ==================== PANEL BANCO ====================
@app.route('/banco/dashboard')
@banco_required
def banco_dashboard():
    try:
        usuario = Usuario.query.get(session['user_id'])
        banco = usuario.banco
        
        tarjetas_count = len(banco.tarjetas)
        tarjetas_aprobadas = sum(1 for t in banco.tarjetas if t.aprobada)
        solicitudes_pendientes = Solicitud.query.filter_by(banco_id=banco.id, estado='pendiente').count()
        
        stats = {
            'tarjetas_count': tarjetas_count,
            'tarjetas_aprobadas': tarjetas_aprobadas,
            'solicitudes_pendientes': solicitudes_pendientes,
            'banco_aprobado': banco.aprobado
        }
        
        return render_template('banco/dashboard.html', banco=banco, stats=stats)
    except Exception as e:
        app.logger.error(f"Error en banco_dashboard: {e}")
        flash('Error al cargar el dashboard del banco', 'danger')
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
        app.logger.error(f"Error en banco_tarjetas: {e}")
        flash('Error al cargar las tarjetas', 'danger')
        return redirect(url_for('banco_dashboard'))

@app.route('/banco/tarjeta/nueva', methods=['GET', 'POST'])
@banco_required
def banco_nueva_tarjeta():
    try:
        usuario = Usuario.query.get(session['user_id'])
        banco = usuario.banco
        
        if not banco.aprobado:
            flash('Tu banco debe estar aprobado para crear tarjetas', 'warning')
            return redirect(url_for('banco_dashboard'))
        
        form = TarjetaForm()
        if form.validate_on_submit():
            tarjeta = Tarjeta(
                nombre=sanitizar_input(form.nombre.data),
                banco_id=banco.id,
                tipo=form.tipo.data,
                cat=form.cat.data,
                anualidad=form.anualidad.data,
                edad_minima=form.edad_minima.data,
                beneficios=sanitizar_input(form.beneficios.data),
                imagen_url=sanitizar_input(form.imagen_url.data)
            )
            db.session.add(tarjeta)
            db.session.flush()
            
            # Crear solicitud de aprobación
            solicitud = Solicitud(
                banco_id=banco.id,
                tipo_solicitud='tarjeta',
                referencia_id=tarjeta.id
            )
            db.session.add(solicitud)
            db.session.commit()
            
            flash('Tarjeta creada. Pendiente de aprobación por el administrador.', 'success')
            return redirect(url_for('banco_tarjetas'))
        
        return render_template('banco/tarjeta_form.html', form=form, titulo='Nueva Tarjeta')
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error en banco_nueva_tarjeta: {e}")
        flash('Error al crear la tarjeta', 'danger')
        return redirect(url_for('banco_tarjetas'))

@app.route('/banco/tarjeta/<int:id>/editar', methods=['GET', 'POST'])
@banco_required
def banco_editar_tarjeta(id):
    try:
        usuario = Usuario.query.get(session['user_id'])
        banco = usuario.banco
        tarjeta = Tarjeta.query.filter_by(id=id, banco_id=banco.id).first_or_404()
        
        form = TarjetaForm(obj=tarjeta)
        if form.validate_on_submit():
            tarjeta.nombre = sanitizar_input(form.nombre.data)
            tarjeta.tipo = form.tipo.data
            tarjeta.cat = form.cat.data
            tarjeta.anualidad = form.anualidad.data
            tarjeta.edad_minima = form.edad_minima.data
            tarjeta.beneficios = sanitizar_input(form.beneficios.data)
            tarjeta.imagen_url = sanitizar_input(form.imagen_url.data)
            tarjeta.aprobada = False  # Requiere nueva aprobación
            
            # Crear nueva solicitud
            solicitud = Solicitud(
                banco_id=banco.id,
                tipo_solicitud='tarjeta',
                referencia_id=tarjeta.id
            )
            db.session.add(solicitud)
            db.session.commit()
            
            flash('Tarjeta actualizada. Pendiente de aprobación.', 'success')
            return redirect(url_for('banco_tarjetas'))
        
        return render_template('banco/tarjeta_form.html', form=form, titulo='Editar Tarjeta', tarjeta=tarjeta)
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error en banco_editar_tarjeta: {e}")
        flash('Error al editar la tarjeta', 'danger')
        return redirect(url_for('banco_tarjetas'))

@app.route('/banco/tarjeta/<int:id>/eliminar', methods=['POST'])
@banco_required
def banco_eliminar_tarjeta(id):
    try:
        usuario = Usuario.query.get(session['user_id'])
        banco = usuario.banco
        tarjeta = Tarjeta.query.filter_by(id=id, banco_id=banco.id).first_or_404()
        
        db.session.delete(tarjeta)
        db.session.commit()
        flash('Tarjeta eliminada exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error en banco_eliminar_tarjeta: {e}")
        flash('Error al eliminar la tarjeta', 'danger')
    
    return redirect(url_for('banco_tarjetas'))

# ==================== MANEJO DE ERRORES ====================
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    app.logger.error(f"Error 500: {error}")
    return render_template('500.html'), 500

# ==================== INICIALIZACIÓN ====================
def init_db():
    with app.app_context():
        try:
            print("🔄 Verificando base de datos...")
            db.create_all()
            
            if not Usuario.query.filter_by(email='admin@policard.com').first():
                admin = Usuario(
                    email='admin@policard.com',
                    password=generate_password_hash('AdminPoliCard2025!'),
                    nombre='Administrador PoliCard',
                    tipo='admin'
                )
                db.session.add(admin)
                db.session.commit()
                print("✅ Admin creado en init_db")
            else:
                print("✅ Base de datos ya inicializada")
                
        except Exception as e:
            print(f"❌ Error en init_db: {e}")

# Inicializar base de datos
init_db()

# ==================== EJECUCIÓN ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)