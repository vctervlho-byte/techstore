"""
seed_db.py — Poblar MongoDB con datos de prueba para TechStore
Ejecutar: python seed_db.py
"""
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
import os, hashlib, random

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME   = os.getenv("DB_NAME", "techstore")

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db     = client[DB_NAME]

def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()

print("🌱 Iniciando seed de la base de datos...")

# ── Limpiar colecciones ───────────────────────────────────────────────────────
db.usuarios.delete_many({})
db.productos.delete_many({})
db.clientes.delete_many({})
db.ventas.delete_many({})

# ── Usuarios ──────────────────────────────────────────────────────────────────
usuarios = [
    {"nombre":"Admin TechStore","email":"admin@techstore.com",
     "password":hash_password("admin123"),"rol":"admin","creado_en":datetime.now(timezone.utc)},
    {"nombre":"María Vendedora","email":"maria@techstore.com",
     "password":hash_password("maria123"),"rol":"vendedor","creado_en":datetime.now(timezone.utc)},
]
res_u = db.usuarios.insert_many(usuarios)
print(f"  ✅ {len(res_u.inserted_ids)} usuarios creados")
print(f"     → admin@techstore.com / admin123")
print(f"     → maria@techstore.com / maria123")

# ── Productos ─────────────────────────────────────────────────────────────────
productos = [
    {"nombre":"Laptop Dell XPS 15","precio":22999,"stock":8,
     "categoria":"Laptops","descripcion":"Intel i7, 16GB RAM, 512GB SSD"},
    {"nombre":"MacBook Air M2","precio":28499,"stock":4,
     "categoria":"Laptops","descripcion":"Apple M2, 8GB RAM, 256GB SSD"},
    {"nombre":"Monitor LG 27\" 4K","precio":8499,"stock":12,
     "categoria":"Monitores","descripcion":"Panel IPS, 60Hz, USB-C"},
    {"nombre":"Teclado Mecánico Logitech","precio":1899,"stock":20,
     "categoria":"Periféricos","descripcion":"Switch Blue, RGB, TKL"},
    {"nombre":"Mouse Inalámbrico MX Master 3","precio":2299,"stock":3,
     "categoria":"Periféricos","descripcion":"Bluetooth, 7 botones"},
    {"nombre":"Audífonos Sony WH-1000XM5","precio":7999,"stock":2,
     "categoria":"Audio","descripcion":"ANC, 30h batería, Bluetooth 5.2"},
    {"nombre":"SSD Samsung 1TB NVMe","precio":1499,"stock":35,
     "categoria":"Almacenamiento","descripcion":"M.2 PCIe 4.0, 7000MB/s"},
    {"nombre":"Webcam Logitech C920","precio":1299,"stock":0,
     "categoria":"Periféricos","descripcion":"Full HD 1080p, micrófono dual"},
    {"nombre":"Hub USB-C 7 en 1","precio":599,"stock":18,
     "categoria":"Accesorios","descripcion":"HDMI, USB 3.0, SD, PD 100W"},
    {"nombre":"Tablet iPad Air 5","precio":14999,"stock":6,
     "categoria":"Tablets","descripcion":"M1 chip, 10.9\", WiFi 6"},
]
now = datetime.now(timezone.utc)
for p in productos:
    p["creado_en"] = now
    p["actualizado_en"] = now
res_p = db.productos.insert_many(productos)
print(f"  ✅ {len(res_p.inserted_ids)} productos creados")

# ── Clientes ──────────────────────────────────────────────────────────────────
clientes = [
    {"nombre":"Juan García","email":"jgarcia@gmail.com",
     "telefono":"667-100-1234","direccion":"Blvd. Madero 450, Culiacán","creado_en":now},
    {"nombre":"Laura Martínez","email":"laura.mtz@hotmail.com",
     "telefono":"667-200-5678","direccion":"Av. Insurgentes 23, Culiacán","creado_en":now},
    {"nombre":"Empresa Tech SRL","email":"compras@techsrl.mx",
     "telefono":"667-300-9012","direccion":"Parque Industrial, Los Mochis","creado_en":now},
    {"nombre":"Roberto Sánchez","email":"rsanchez@outlook.com",
     "telefono":"667-400-3456","direccion":"Calle Hidalgo 7, Mazatlán","creado_en":now},
]
res_c = db.clientes.insert_many(clientes)
clientes_ids = res_c.inserted_ids
print(f"  ✅ {len(clientes_ids)} clientes creados")

# ── Ventas de ejemplo ─────────────────────────────────────────────────────────
prods = list(db.productos.find())
admin_id = str(res_u.inserted_ids[0])

ventas = []
for i in range(8):
    num_items = random.randint(1, 3)
    items_sel = random.sample(prods, min(num_items, len(prods)))
    items_venta = []
    total = 0
    for prod in items_sel:
        qty = random.randint(1, 2)
        sub = prod["precio"] * qty
        total += sub
        items_venta.append({
            "producto_id":    str(prod["_id"]),
            "nombre":         prod["nombre"],
            "precio_unitario":prod["precio"],
            "cantidad":       qty,
            "subtotal":       sub
        })
    cliente = random.choice(clientes)
    ventas.append({
        "cliente":     {"cliente_id": str(clientes_ids[clientes.index(cliente)]),
                        "nombre": cliente["nombre"]},
        "items":       items_venta,
        "total":       round(total, 2),
        "fecha":       datetime.now(timezone.utc) - timedelta(days=random.randint(0,30)),
        "vendedor_id": admin_id,
        "vendedor":    "Admin TechStore",
        "estado":      "completada"
    })

db.ventas.insert_many(ventas)
print(f"  ✅ {len(ventas)} ventas de ejemplo creadas")

# ── Índices recomendados ──────────────────────────────────────────────────────
db.usuarios.create_index("email", unique=True)
db.productos.create_index("categoria")
db.productos.create_index("stock")
db.ventas.create_index("fecha")
db.ventas.create_index("total")
print("  ✅ Índices de MongoDB creados")

print("\n🎉 ¡Base de datos lista! Ejecuta: python app.py")
