from app import app, db, Tarjeta

with app.app_context():
    db.drop_all()
    db.create_all()
    
    tarjetas = [
        Tarjeta(nombre='BBVA Azul', banco='BBVA', tipo='estudiante', cat=45.5, anualidad=0, edad_minima=18, beneficios='Sin anualidad, cashback'),
        Tarjeta(nombre='Santander Like U', banco='Santander', tipo='joven', cat=42.0, anualidad=500, edad_minima=18, beneficios='Descuentos en entretenimiento'),
        Tarjeta(nombre='Banamex Tec', banco='Banamex', tipo='estudiante', cat=38.5, anualidad=0, edad_minima=18, beneficios='Sin anualidad, seguro'),
        Tarjeta(nombre='HSBC Zero', banco='HSBC', tipo='joven', cat=50.0, anualidad=0, edad_minima=21, beneficios='Meses sin intereses'),
        Tarjeta(nombre='Banorte Clásica', banco='Banorte', tipo='clasica', cat=55.0, anualidad=800, edad_minima=22, beneficios='Puntos recompensa'),
        Tarjeta(nombre='Nu Ultravioleta', banco='Nu', tipo='estudiante', cat=35.0, anualidad=0, edad_minima=18, beneficios='Cashback automático'),
    ]
    
    for tarjeta in tarjetas:
        db.session.add(tarjeta)
    
    db.session.commit()
    print("Base de datos creada exitosamente")