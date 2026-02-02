import os
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
import sqlite3

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///facturacion.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'clave-secreta-facturacion'
db = SQLAlchemy(app)

# Modelos de Base de Datos
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True)
    nombre = db.Column(db.String(100))
    direccion = db.Column(db.String(200))
    telefono = db.Column(db.String(50))
    cuit = db.Column(db.String(50))
    iva_condicion = db.Column(db.String(50), default="CONSUMIDOR FINAL")
    email = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.now)
    
class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.String(200))
    costo = db.Column(db.Float, default=0.0)
    precio_1 = db.Column(db.Float, default=0.0)
    precio_2 = db.Column(db.Float, default=0.0)
    precio_3 = db.Column(db.Float, default=0.0)
    precio_4 = db.Column(db.Float, default=0.0)
    stock = db.Column(db.Float, default=0.0)
    unidad_medida = db.Column(db.String(20), default='unidad')
    created_at = db.Column(db.DateTime, default=datetime.now)
    
class ListaPrecio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    margen = db.Column(db.Float)  # Porcentaje de ganancia
    activa = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
class Factura(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(50), unique=True)
    fecha = db.Column(db.DateTime, default=datetime.now)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'))
    cliente = db.relationship('Cliente')
    vendedor = db.Column(db.String(100), default="TITULAR DEL COMERCIO")
    forma_entrega = db.Column(db.String(50))
    cond_venta = db.Column(db.String(50), default="CONTADO")
    total = db.Column(db.Float, default=0.0)
    iva = db.Column(db.Float, default=0.0)
    peso = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
class FacturaDetalle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    factura_id = db.Column(db.Integer, db.ForeignKey('factura.id'))
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'))
    producto = db.relationship('Producto')
    cantidad = db.Column(db.Float, default=1.0)
    precio_unitario = db.Column(db.Float, default=0.0)
    descuento = db.Column(db.Float, default=0.0)
    subtotal = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.now)

# Crear base de datos y algunos datos de prueba
def crear_datos_iniciales():
    with app.app_context():
        db.create_all()
        
        # Crear un cliente de prueba si no existe
        if not Cliente.query.first():
            cliente = Cliente(
                codigo="601",
                nombre="Emiliano Otero",
                direccion="Dirección de ejemplo",
                telefono="123456789",
                cuit="11-11111111-3",
                iva_condicion="CONSUMIDOR FINAL"
            )
            db.session.add(cliente)
            db.session.commit()
            print("Cliente de prueba creado: Emiliano Otero")

# Rutas de la API
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/importar-excel', methods=['POST'])
def importar_excel():
    """Importa productos desde un archivo Excel"""
    if 'file' not in request.files:
        return jsonify({'error': 'No se encontró el archivo'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No se seleccionó ningún archivo'}), 400
    
    try:
        # Leer el archivo Excel
        df = pd.read_excel(file)
        
        productos_importados = 0
        productos_actualizados = 0
        
        # Procesar cada fila
        for index, row in df.iterrows():
            codigo = str(row.get('CODIGO', '')).strip()
            
            if not codigo or codigo == 'nan':
                continue
                
            # Verificar si el producto ya existe
            producto_existente = Producto.query.filter_by(codigo=codigo).first()
            
            if producto_existente:
                # Actualizar producto existente
                producto_existente.descripcion = str(row.get('DETALLE', ''))[:200]
                producto_existente.costo = float(row.get('COSTO', 0) or 0)
                producto_existente.precio_1 = float(row.get('PRECIO_1', 0) or 0)
                producto_existente.precio_2 = float(row.get('PRECIO_2', 0) or 0)
                producto_existente.precio_3 = float(row.get('PRECIO_3', 0) or 0)
                producto_existente.precio_4 = float(row.get('PRECIO_4', 0) or 0)
                productos_actualizados += 1
            else:
                # Crear nuevo producto
                producto = Producto(
                    codigo=codigo,
                    descripcion=str(row.get('DETALLE', ''))[:200],
                    costo=float(row.get('COSTO', 0) or 0),
                    precio_1=float(row.get('PRECIO_1', 0) or 0),
                    precio_2=float(row.get('PRECIO_2', 0) or 0),
                    precio_3=float(row.get('PRECIO_3', 0) or 0),
                    precio_4=float(row.get('PRECIO_4', 0) or 0)
                )
                db.session.add(producto)
                productos_importados += 1
        
        db.session.commit()
        
        return jsonify({
            'message': f'Importación completada',
            'importados': productos_importados,
            'actualizados': productos_actualizados,
            'total': productos_importados + productos_actualizados
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/crear-lista-precios', methods=['POST'])
def crear_lista_precios():
    """Crea una nueva lista de precios con margen específico"""
    data = request.json
    nombre = data.get('nombre', '').strip()
    margen = float(data.get('margen', 0))
    
    if not nombre:
        return jsonify({'error': 'El nombre es requerido'}), 400
    
    # Crear la lista de precios
    lista = ListaPrecio(nombre=nombre, margen=margen)
    db.session.add(lista)
    db.session.commit()
    
    return jsonify({
        'message': 'Lista de precios creada correctamente',
        'lista_id': lista.id,
        'nombre': lista.nombre,
        'margen': lista.margen
    })

@app.route('/api/clientes')
def obtener_clientes():
    """Obtiene todos los clientes"""
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    return jsonify([{
        'id': c.id,
        'codigo': c.codigo,
        'nombre': c.nombre,
        'direccion': c.direccion,
        'telefono': c.telefono,
        'cuit': c.cuit,
        'iva_condicion': c.iva_condicion
    } for c in clientes])

@app.route('/api/productos')
def obtener_productos():
    """Obtiene todos los productos"""
    productos = Producto.query.order_by(Producto.descripcion).all()
    return jsonify([{
        'id': p.id,
        'codigo': p.codigo,
        'descripcion': p.descripcion,
        'costo': p.costo,
        'precio_1': p.precio_1,
        'precio_2': p.precio_2,
        'precio_3': p.precio_3,
        'precio_4': p.precio_4,
        'stock': p.stock
    } for p in productos])

@app.route('/api/buscar-producto/<codigo>')
def buscar_producto(codigo):
    """Busca un producto por código"""
    producto = Producto.query.filter_by(codigo=codigo).first()
    if producto:
        return jsonify({
            'id': producto.id,
            'codigo': producto.codigo,
            'descripcion': producto.descripcion,
            'precio_1': producto.precio_1,
            'precio_2': producto.precio_2,
            'precio_3': producto.precio_3,
            'precio_4': producto.precio_4
        })
    return jsonify({'error': 'Producto no encontrado'}), 404

@app.route('/api/crear-factura', methods=['POST'])
def crear_factura():
    """Crea una nueva factura"""
    data = request.json
    cliente_id = data.get('cliente_id')
    productos = data.get('productos', [])
    vendedor = data.get('vendedor', 'TITULAR DEL COMERCIO')
    forma_entrega = data.get('forma_entrega', '')
    cond_venta = data.get('cond_venta', 'CONTADO')
    
    if not cliente_id:
        return jsonify({'error': 'Seleccione un cliente'}), 400
    
    if not productos:
        return jsonify({'error': 'Agregue productos a la factura'}), 400
    
    # Obtener el último número de factura
    ultima_factura = Factura.query.order_by(Factura.id.desc()).first()
    if ultima_factura:
        ultimo_numero = int(ultima_factura.numero.split('-')[-1]) if '-' in ultima_factura.numero else 0
    else:
        ultimo_numero = 0
    
    # Crear número de factura
    numero_factura = f"0001-{ultimo_numero + 1:08d}"
    
    # Crear la factura
    factura = Factura(
        numero=numero_factura,
        cliente_id=cliente_id,
        vendedor=vendedor,
        forma_entrega=forma_entrega,
        cond_venta=cond_venta,
        total=0.0
    )
    db.session.add(factura)
    db.session.flush()
    
    # Agregar productos a la factura
    total = 0
    for item in productos:
        producto = Producto.query.get(item['producto_id'])
        if producto:
            precio = float(item.get('precio', producto.precio_1))
            cantidad = float(item.get('cantidad', 1))
            subtotal = cantidad * precio
            
            detalle = FacturaDetalle(
                factura_id=factura.id,
                producto_id=producto.id,
                cantidad=cantidad,
                precio_unitario=precio,
                subtotal=subtotal
            )
            db.session.add(detalle)
            total += subtotal
    
    # Actualizar total
    factura.total = total
    db.session.commit()
    
    return jsonify({
        'message': 'Factura creada correctamente',
        'factura_id': factura.id,
        'numero': factura.numero,
        'total': total,
        'fecha': factura.fecha.strftime('%d/%m/%Y %H:%M')
    })

@app.route('/api/factura/<int:factura_id>/pdf')
def generar_pdf_factura(factura_id):
    factura = Factura.query.get_or_404(factura_id)
    buffer = io.BytesIO()
    
    # Configuración del documento (A4)
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    estilo_titulo = ParagraphStyle('Titulo', parent=styles['Normal'], fontSize=16, leading=20, alignment=0)
    estilo_negrita = ParagraphStyle('Negrita', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold')
    estilo_tabla = TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
    ])

    # --- ENCABEZADO TIPO EMIOTERO-1 ---
    header_data = [
        [Paragraph("<b>Presupuesto</b>", estilo_titulo), "Datos Presupuesto"],
        ["Arcor", f"Numero de Presupuesto {factura.numero}"],
        ["Direccion", f"Punto de Venta: 0001"],
        ["Localidad, Provincia", f"Fecha: {factura.fecha.strftime('%d/%m/%Y')}"],
        ["CUIT: 11-11111111-3", f"Vendedor: {factura.vendedor}"]
    ]
    header_table = Table(header_data, colWidths=[300, 230])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
    ]))
    elements.append(header_table)
    elements.append(Paragraph("<br/><br/>", styles['Normal']))

    # --- DATOS DEL CLIENTE ---
    cliente_info = [
        ["Codigo:", factura.cliente.codigo if factura.cliente else "S/N", "Señor:", factura.cliente.nombre if factura.cliente else "Consumidor Final"],
        ["IVA:", factura.cliente.iva_condicion if factura.cliente else "CONSUMIDOR FINAL", "Tel:", factura.cliente.telefono or ""],
        ["Cond. Venta:", factura.cond_venta, "Entrega:", factura.forma_entrega or ""]
    ]
    cliente_table = Table(cliente_info, colWidths=[80, 185, 80, 185])
    cliente_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('SIZE', (0,0), (-1,-1), 10),
    ]))
    elements.append(cliente_table)
    elements.append(Paragraph("<br/>", styles['Normal']))

    # --- TABLA DE PRODUCTOS ---
    data = [["ARTICULO", "Descripción", "Pre Uni", "Can", "PLU x Can", "Desc", "TOTAL"]]
    
    detalles = FacturaDetalle.query.filter_by(factura_id=factura.id).all()
    for item in detalles:
        data.append([
            item.producto.codigo,
            item.producto.descripcion,
            f"{item.precio_unitario:,.2f}",
            f"{item.cantidad:,.0f}",
            f"{item.subtotal:,.2f}",
            "0.00",
            f"{item.subtotal:,.2f}"
        ])

    # Fila de Totales
    data.append(["", "", "", "", "", Paragraph("<b>TOTAL</b>", estilo_negrita), f"{factura.total:,.2f}"])
    
    tabla_productos = Table(data, colWidths=[60, 180, 60, 50, 70, 50, 60])
    tabla_productos.setStyle(estilo_tabla)
    elements.append(tabla_productos)

    # --- PIE DE PÁGINA ---
    elements.append(Paragraph("<br/><br/>", styles['Normal']))
    elements.append(Paragraph("Gracias por su compra", styles['Italic']))

    # Generar PDF
    doc.build(elements)
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=False,
        download_name=f'factura_{factura.numero}.pdf',
        mimetype='application/pdf'
    )

@app.route('/api/crear-cliente', methods=['POST'])
def crear_cliente():
    """Crea un nuevo cliente"""
    data = request.json
    
    cliente = Cliente(
        codigo=data.get('codigo', ''),
        nombre=data.get('nombre', ''),
        direccion=data.get('direccion', ''),
        telefono=data.get('telefono', ''),
        cuit=data.get('cuit', ''),
        iva_condicion=data.get('iva_condicion', 'CONSUMIDOR FINAL'),
        email=data.get('email', '')
    )
    
    db.session.add(cliente)
    db.session.commit()
    
    return jsonify({
        'message': 'Cliente creado correctamente',
        'cliente_id': cliente.id
    })

# Ruta para limpiar datos de prueba
@app.route('/api/limpiar-datos', methods=['POST'])
def limpiar_datos():
    """Elimina todos los datos (solo para desarrollo)"""
    try:
        # Eliminar todas las tablas
        FacturaDetalle.query.delete()
        Factura.query.delete()
        Producto.query.delete()
        Cliente.query.delete()
        ListaPrecio.query.delete()
        
        db.session.commit()
        
        # Crear cliente de prueba
        cliente = Cliente(
            codigo="601",
            nombre="Emiliano Otero",
            direccion="Dirección de ejemplo",
            telefono="123456789",
            cuit="11-11111111-3",
            iva_condicion="CONSUMIDOR FINAL"
        )
        db.session.add(cliente)
        db.session.commit()
        
        return jsonify({'message': 'Datos limpiados y cliente de prueba creado'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    crear_datos_iniciales()
    app.run(debug=True, host='0.0.0.0', port=5000)
