from flask import Flask, render_template, request, flash, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField, TextAreaField, FloatField, PasswordField
from wtforms.validators import DataRequired, NumberRange, Email, Length, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'policard2025secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///policard.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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
    tipo = SelectField('Tipo', choices=[('estudiante', 'Estudiante'), ('joven', 'Joven'), ('clasica', 'Clásica')], validators=[DataRequired()])
    cat = FloatField('CAT (%)', validators=[DataRequired(), NumberRange(min=0)])
    anualidad = FloatField('Anualidad ($)', validators=[DataRequired(), NumberRange(min=0)])
    edad_minima = IntegerField('Edad Mínima', validators=[DataRequired(), NumberRange(min=18, max=100)])
    beneficios = TextAreaField('Beneficios')
    imagen_url = StringField('URL de la Imagen')

class BusquedaForm(FlaskForm):
    edad = IntegerField('Edad', validators=[DataRequired(), NumberRange(min=18, max=100)])
    tipo = SelectField('Tipo', choices=[('estudiante', 'Estudiante'), ('joven', 'Joven'), ('clasica', 'Clásica')])

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
        return f(*args, **kwargs)
    return decorated_function

# ==================== RUTAS PÚBLICAS ====================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/tarjetas')
def tarjetas():
    todas_tarjetas = Tarjeta.query.filter_by(aprobada=True).all()
    return render_template('tarjetas.html', tarjetas=todas_tarjetas)

@app.route('/buscar', methods=['GET', 'POST'])
def buscar():
    form = BusquedaForm()
    resultados = []
    if form.validate_on_submit():
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
    return render_template('buscar.html', form=form, resultados=resultados)

@app.route('/educacion')
def educacion():
    return render_template('educacion.html')

@app.route('/calculadora')
def calculadora():
    return render_template('calculadora.html')

# ==================== AUTENTICACIÓN ====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
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
    
    return render_template('login.html', form=form)

@app.route('/registro-banco', methods=['GET', 'POST'])
def registro_banco():
    form = RegistroBancoForm()
    if form.validate_on_submit():
        # Verificar si el email ya existe
        if Usuario.query.filter_by(email=form.email.data).first():
            flash('Este email ya está registrado', 'danger')
            return redirect(url_for('registro_banco'))
        
        # Crear usuario
        usuario = Usuario(
            email=form.email.data,
            password=generate_password_hash(form.password.data),
            nombre=form.nombre_contacto.data,
            tipo='banco'
        )
        db.session.add(usuario)
        db.session.flush()
        
        # Crear banco
        banco = Banco(
            usuario_id=usuario.id,
            nombre_banco=form.nombre_banco.data,
            telefono=form.telefono.data,
            sitio_web=form.sitio_web.data,
            descripcion=form.descripcion.data
        )
        db.session.add(banco)
        
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
    usuario = Usuario.query.get(session['user_id'])
    if usuario.tipo == 'admin':
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('banco_dashboard'))

# ==================== PANEL ADMIN ====================
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
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

@app.route('/admin/solicitudes')
@admin_required
def admin_solicitudes():
    solicitudes = Solicitud.query.filter_by(estado='pendiente').order_by(Solicitud.fecha_solicitud.desc()).all()
    return render_template('admin/solicitudes.html', solicitudes=solicitudes)

@app.route('/admin/solicitud/<int:id>/aprobar', methods=['POST'])
@admin_required
def aprobar_solicitud(id):
    solicitud = Solicitud.query.get_or_404(id)
    solicitud.estado = 'aprobada'
    solicitud.fecha_respuesta = datetime.utcnow()
    
    if solicitud.tipo_solicitud == 'banco':
        banco = Banco.query.get(solicitud.referencia_id)
        banco.aprobado = True
        banco.fecha_aprobacion = datetime.utcnow()
    elif solicitud.tipo_solicitud == 'tarjeta':
        tarjeta = Tarjeta.query.get(solicitud.referencia_id)
        tarjeta.aprobada = True
        tarjeta.fecha_aprobacion = datetime.utcnow()
    
    db.session.commit()
    flash('Solicitud aprobada exitosamente', 'success')
    return redirect(url_for('admin_solicitudes'))

@app.route('/admin/solicitud/<int:id>/rechazar', methods=['POST'])
@admin_required
def rechazar_solicitud(id):
    solicitud = Solicitud.query.get_or_404(id)
    solicitud.estado = 'rechazada'
    solicitud.fecha_respuesta = datetime.utcnow()
    solicitud.comentario_admin = request.form.get('comentario', '')
    
    db.session.commit()
    flash('Solicitud rechazada', 'info')
    return redirect(url_for('admin_solicitudes'))

@app.route('/admin/bancos')
@admin_required
def admin_bancos():
    bancos = Banco.query.all()
    return render_template('admin/bancos.html', bancos=bancos)

@app.route('/admin/tarjetas')
@admin_required
def admin_tarjetas():
    tarjetas = Tarjeta.query.all()
    return render_template('admin/tarjetas.html', tarjetas=tarjetas)

# ==================== PANEL BANCO ====================
@app.route('/banco/dashboard')
@banco_required
def banco_dashboard():
    usuario = Usuario.query.get(session['user_id'])
    banco = usuario.banco
    
    if not banco:
        flash('No se encontró información del banco', 'danger')
        return redirect(url_for('logout'))
    
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

@app.route('/banco/tarjetas')
@banco_required
def banco_tarjetas():
    usuario = Usuario.query.get(session['user_id'])
    banco = usuario.banco
    tarjetas = banco.tarjetas
    return render_template('banco/tarjetas.html', tarjetas=tarjetas, banco=banco)

@app.route('/banco/tarjeta/nueva', methods=['GET', 'POST'])
@banco_required
def banco_nueva_tarjeta():
    usuario = Usuario.query.get(session['user_id'])
    banco = usuario.banco
    
    if not banco.aprobado:
        flash('Tu banco debe estar aprobado para crear tarjetas', 'warning')
        return redirect(url_for('banco_dashboard'))
    
    form = TarjetaForm()
    if form.validate_on_submit():
        tarjeta = Tarjeta(
            nombre=form.nombre.data,
            banco_id=banco.id,
            tipo=form.tipo.data,
            cat=form.cat.data,
            anualidad=form.anualidad.data,
            edad_minima=form.edad_minima.data,
            beneficios=form.beneficios.data,
            imagen_url=form.imagen_url.data
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

@app.route('/banco/tarjeta/<int:id>/editar', methods=['GET', 'POST'])
@banco_required
def banco_editar_tarjeta(id):
    usuario = Usuario.query.get(session['user_id'])
    banco = usuario.banco
    tarjeta = Tarjeta.query.filter_by(id=id, banco_id=banco.id).first_or_404()
    
    form = TarjetaForm(obj=tarjeta)
    if form.validate_on_submit():
        tarjeta.nombre = form.nombre.data
        tarjeta.tipo = form.tipo.data
        tarjeta.cat = form.cat.data
        tarjeta.anualidad = form.anualidad.data
        tarjeta.edad_minima = form.edad_minima.data
        tarjeta.beneficios = form.beneficios.data
        tarjeta.imagen_url = form.imagen_url.data
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

@app.route('/banco/tarjeta/<int:id>/eliminar', methods=['POST'])
@banco_required
def banco_eliminar_tarjeta(id):
    usuario = Usuario.query.get(session['user_id'])
    banco = usuario.banco
    tarjeta = Tarjeta.query.filter_by(id=id, banco_id=banco.id).first_or_404()
    
    db.session.delete(tarjeta)
    db.session.commit()
    flash('Tarjeta eliminada exitosamente', 'success')
    return redirect(url_for('banco_tarjetas'))

# ==================== INICIALIZACIÓN ====================
def init_db():
    with app.app_context():
        db.create_all()
        
        # Crear admin por defecto si no existe
        if not Usuario.query.filter_by(email='admin@policard.com').first():
            admin = Usuario(
                email='admin@policard.com',
                password=generate_password_hash('admin123'),
                nombre='Administrador PoliCard',
                tipo='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Usuario admin creado: admin@policard.com / admin123")

if __name__ == '__main__':
    init_db()
    app.run(debug=True)