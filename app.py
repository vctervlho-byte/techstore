from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from datetime import datetime, timezone
import os
import json
import hashlib

# ─── Cargar variables de entorno ──────────────────────────────────────────────
load_dotenv()

# ─── Inicializar Flask ────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-cambiar-en-produccion")
CORS(app)

# ─── Conexión a MongoDB ───────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME   = os.getenv("DB_NAME", "techstore")

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")           # verifica conexión
    db = client[DB_NAME]
    print(f"✅  Conectado a MongoDB — base de datos: {DB_NAME}")
except (ConnectionFailure, ServerSelectionTimeoutError) as e:
    print(f"❌  Error al conectar a MongoDB: {e}")
    db = None

# ─── Helper: serializar documentos BSON ──────────────────────────────────────
def serialize(doc):
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize(d) for d in doc]
    doc["_id"] = str(doc["_id"])
    return doc

# ─── Helper: hash de contraseña ───────────────────────────────────────────────
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ─── Helper: verificar sesión ────────────────────────────────────────────────
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "No autorizado"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINAS (Frontend)
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    return render_template("index.html", usuario=session.get("nombre"))

@app.route("/login")
def login_page():
    if "user_id" in session:
        return redirect(url_for("index"))
    return render_template("login.html")

# ═══════════════════════════════════════════════════════════════════════════════
# API — AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/auth/registro", methods=["POST"])
def registro():
    data = request.get_json()
    nombre   = data.get("nombre", "").strip()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")
    rol      = data.get("rol", "vendedor")

    if not nombre or not email or not password:
        return jsonify({"error": "Todos los campos son requeridos"}), 400
    if db.usuarios.find_one({"email": email}):
        return jsonify({"error": "El email ya está registrado"}), 409

    usuario = {
        "nombre":    nombre,
        "email":     email,
        "password":  hash_password(password),
        "rol":       rol,
        "creado_en": datetime.now(timezone.utc)
    }
    result = db.usuarios.insert_one(usuario)
    return jsonify({"mensaje": "Usuario registrado", "id": str(result.inserted_id)}), 201

@app.route("/api/auth/login", methods=["POST"])
def login():
    data     = request.get_json()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")

    usuario = db.usuarios.find_one({
        "email":    email,
        "password": hash_password(password)
    })
    if not usuario:
        return jsonify({"error": "Credenciales incorrectas"}), 401

    session["user_id"] = str(usuario["_id"])
    session["nombre"]  = usuario["nombre"]
    session["rol"]     = usuario["rol"]
    return jsonify({"mensaje": "Login exitoso", "nombre": usuario["nombre"], "rol": usuario["rol"]})

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"mensaje": "Sesión cerrada"})

# ═══════════════════════════════════════════════════════════════════════════════
# API — PRODUCTOS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/productos", methods=["GET"])
@login_required
def get_productos():
    productos = list(db.productos.find())
    return jsonify(serialize(productos))

@app.route("/api/productos/<id>", methods=["GET"])
@login_required
def get_producto(id):
    try:
        producto = db.productos.find_one({"_id": ObjectId(id)})
        if not producto:
            return jsonify({"error": "Producto no encontrado"}), 404
        return jsonify(serialize(producto))
    except InvalidId:
        return jsonify({"error": "ID inválido"}), 400

@app.route("/api/productos", methods=["POST"])
@login_required
def crear_producto():
    data = request.get_json()
    nombre   = data.get("nombre", "").strip()
    precio   = data.get("precio")
    stock    = data.get("stock", 0)
    categoria= data.get("categoria", "General").strip()
    descripcion = data.get("descripcion", "").strip()

    if not nombre or precio is None:
        return jsonify({"error": "Nombre y precio son requeridos"}), 400

    producto = {
        "nombre":      nombre,
        "precio":      float(precio),
        "stock":       int(stock),
        "categoria":   categoria,
        "descripcion": descripcion,
        "creado_en":   datetime.now(timezone.utc),
        "actualizado_en": datetime.now(timezone.utc)
    }
    result = db.productos.insert_one(producto)
    return jsonify({"mensaje": "Producto creado", "id": str(result.inserted_id)}), 201

@app.route("/api/productos/<id>", methods=["PUT"])
@login_required
def actualizar_producto(id):
    try:
        data = request.get_json()
        campos = {}
        if "nombre"      in data: campos["nombre"]      = data["nombre"].strip()
        if "precio"      in data: campos["precio"]      = float(data["precio"])
        if "stock"       in data: campos["stock"]       = int(data["stock"])
        if "categoria"   in data: campos["categoria"]   = data["categoria"].strip()
        if "descripcion" in data: campos["descripcion"] = data["descripcion"].strip()
        campos["actualizado_en"] = datetime.now(timezone.utc)

        result = db.productos.update_one({"_id": ObjectId(id)}, {"$set": campos})
        if result.matched_count == 0:
            return jsonify({"error": "Producto no encontrado"}), 404
        return jsonify({"mensaje": "Producto actualizado"})
    except InvalidId:
        return jsonify({"error": "ID inválido"}), 400

@app.route("/api/productos/<id>", methods=["DELETE"])
@login_required
def eliminar_producto(id):
    try:
        result = db.productos.delete_one({"_id": ObjectId(id)})
        if result.deleted_count == 0:
            return jsonify({"error": "Producto no encontrado"}), 404
        return jsonify({"mensaje": "Producto eliminado"})
    except InvalidId:
        return jsonify({"error": "ID inválido"}), 400

# ─── Consultas especiales ─────────────────────────────────────────────────────

@app.route("/api/productos/stock-bajo", methods=["GET"])
@login_required
def productos_stock_bajo():
    """Productos con stock menor a 5"""
    productos = list(db.productos.find({"stock": {"$lt": 5}}))
    return jsonify(serialize(productos))

# ═══════════════════════════════════════════════════════════════════════════════
# API — CLIENTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/clientes", methods=["GET"])
@login_required
def get_clientes():
    clientes = list(db.clientes.find())
    return jsonify(serialize(clientes))

@app.route("/api/clientes", methods=["POST"])
@login_required
def crear_cliente():
    data = request.get_json()
    nombre   = data.get("nombre", "").strip()
    email    = data.get("email", "").strip().lower()
    telefono = data.get("telefono", "").strip()
    direccion= data.get("direccion", "").strip()

    if not nombre:
        return jsonify({"error": "El nombre es requerido"}), 400

    cliente = {
        "nombre":    nombre,
        "email":     email,
        "telefono":  telefono,
        "direccion": direccion,
        "creado_en": datetime.now(timezone.utc)
    }
    result = db.clientes.insert_one(cliente)
    return jsonify({"mensaje": "Cliente registrado", "id": str(result.inserted_id)}), 201

@app.route("/api/clientes/<id>", methods=["PUT"])
@login_required
def actualizar_cliente(id):
    try:
        data   = request.get_json()
        campos = {}
        if "nombre"    in data: campos["nombre"]    = data["nombre"].strip()
        if "email"     in data: campos["email"]     = data["email"].strip().lower()
        if "telefono"  in data: campos["telefono"]  = data["telefono"].strip()
        if "direccion" in data: campos["direccion"] = data["direccion"].strip()

        result = db.clientes.update_one({"_id": ObjectId(id)}, {"$set": campos})
        if result.matched_count == 0:
            return jsonify({"error": "Cliente no encontrado"}), 404
        return jsonify({"mensaje": "Cliente actualizado"})
    except InvalidId:
        return jsonify({"error": "ID inválido"}), 400

# ═══════════════════════════════════════════════════════════════════════════════
# API — VENTAS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/ventas", methods=["GET"])
@login_required
def get_ventas():
    ventas = list(db.ventas.find().sort("fecha", -1))
    return jsonify(serialize(ventas))

@app.route("/api/ventas", methods=["POST"])
@login_required
def crear_venta():
    data       = request.get_json()
    cliente_id = data.get("cliente_id")
    items      = data.get("items", [])   # [{producto_id, cantidad, precio_unitario}]

    if not items:
        return jsonify({"error": "La venta debe tener al menos un producto"}), 400

    # Validar y construir items
    items_venta = []
    total = 0.0

    for item in items:
        try:
            producto = db.productos.find_one({"_id": ObjectId(item["producto_id"])})
        except (InvalidId, KeyError):
            return jsonify({"error": f"Producto inválido: {item.get('producto_id')}"}), 400

        if not producto:
            return jsonify({"error": f"Producto no encontrado: {item.get('producto_id')}"}), 404

        cantidad = int(item.get("cantidad", 1))
        if producto["stock"] < cantidad:
            return jsonify({"error": f"Stock insuficiente para {producto['nombre']}"}), 400

        precio_unitario = producto["precio"]
        subtotal        = precio_unitario * cantidad
        total          += subtotal

        items_venta.append({
            "producto_id":    str(producto["_id"]),
            "nombre":         producto["nombre"],
            "precio_unitario":precio_unitario,
            "cantidad":       cantidad,
            "subtotal":       subtotal
        })

        # Descontar stock
        db.productos.update_one(
            {"_id": producto["_id"]},
            {"$inc": {"stock": -cantidad},
             "$set": {"actualizado_en": datetime.now(timezone.utc)}}
        )

    # Buscar datos del cliente
    cliente_info = {}
    if cliente_id:
        try:
            c = db.clientes.find_one({"_id": ObjectId(cliente_id)})
            if c:
                cliente_info = {"cliente_id": str(c["_id"]), "nombre": c["nombre"]}
        except InvalidId:
            pass

    venta = {
        "cliente":      cliente_info,
        "items":        items_venta,
        "total":        round(total, 2),
        "fecha":        datetime.now(timezone.utc),
        "vendedor_id":  session["user_id"],
        "vendedor":     session["nombre"],
        "estado":       "completada"
    }
    result = db.ventas.insert_one(venta)
    venta["_id"] = str(result.inserted_id)
    venta["fecha"] = venta["fecha"].isoformat()
    # limpiar keys no serializables
    return jsonify({"mensaje": "Venta registrada", "venta": serialize(venta)}), 201

# ═══════════════════════════════════════════════════════════════════════════════
# API — REPORTES / CONSULTAS MONGODB
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/reportes/resumen", methods=["GET"])
@login_required
def reporte_resumen():
    """Total de ventas, clientes y productos"""
    total_ventas    = db.ventas.count_documents({})
    total_clientes  = db.clientes.count_documents({})
    total_productos = db.productos.count_documents({})
    stock_bajo      = db.productos.count_documents({"stock": {"$lt": 5}})

    # Total vendido (suma de todos los totales)
    pipeline_total = [{"$group": {"_id": None, "total": {"$sum": "$total"}}}]
    res = list(db.ventas.aggregate(pipeline_total))
    total_dinero = res[0]["total"] if res else 0

    # Ventas mayores a $10,000
    ventas_grandes = db.ventas.count_documents({"total": {"$gt": 10000}})

    return jsonify({
        "total_ventas":    total_ventas,
        "total_clientes":  total_clientes,
        "total_productos": total_productos,
        "stock_bajo":      stock_bajo,
        "total_vendido":   round(total_dinero, 2),
        "ventas_grandes":  ventas_grandes
    })

@app.route("/api/reportes/productos-mas-vendidos", methods=["GET"])
@login_required
def productos_mas_vendidos():
    """Top 10 productos más vendidos por cantidad"""
    pipeline = [
        {"$unwind": "$items"},
        {"$group": {
            "_id":      "$items.nombre",
            "cantidad": {"$sum": "$items.cantidad"},
            "ingresos": {"$sum": "$items.subtotal"}
        }},
        {"$sort": {"cantidad": -1}},
        {"$limit": 10}
    ]
    resultado = list(db.ventas.aggregate(pipeline))
    return jsonify(resultado)

@app.route("/api/reportes/ventas-por-fecha", methods=["GET"])
@login_required
def ventas_por_fecha():
    """Ventas agrupadas por día"""
    pipeline = [
        {"$group": {
            "_id": {
                "year":  {"$year":  "$fecha"},
                "month": {"$month": "$fecha"},
                "day":   {"$dayOfMonth": "$fecha"}
            },
            "total_dia":   {"$sum": "$total"},
            "num_ventas":  {"$sum": 1}
        }},
        {"$sort": {"_id.year": -1, "_id.month": -1, "_id.day": -1}},
        {"$limit": 30}
    ]
    resultado = list(db.ventas.aggregate(pipeline))
    # Formatear fechas
    for r in resultado:
        d = r["_id"]
        r["fecha"] = f"{d['year']}-{d['month']:02d}-{d['day']:02d}"
    return jsonify(resultado)

@app.route("/api/reportes/inventario", methods=["GET"])
@login_required
def inventario():
    """Todos los productos con su stock actual"""
    productos = list(db.productos.find({}, {"nombre":1,"stock":1,"precio":1,"categoria":1}))
    return jsonify(serialize(productos))

# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/health")
def health():
    try:
        client.admin.command("ping")
        estado_db = "conectado"
    except Exception:
        estado_db = "desconectado"
    return jsonify({"estado": "ok", "mongodb": estado_db})

# ─── Arrancar servidor ────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, port=port)
