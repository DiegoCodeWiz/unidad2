# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
import requests
import re
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'clave_secreta_super_segura_2026'

# ==================== CONFIGURACIÓN reCAPTCHA ====================
RECAPTCHA_SITE_KEY = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"
RECAPTCHA_SECRET_KEY = "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"

# ==================== CONFIGURACIÓN SQLITE ====================
DB_NAME = "usuarios.db"

def get_connection():
    """Crea y retorna una conexión a SQLite"""
    try:
        conn = sqlite3.connect(DB_NAME)
        return conn
    except Exception as e:
        print(f"Error conectando a SQLite: {e}")
        return None

def require_login():
    if 'user_id' not in session:
        flash('Inicia sesión primero', 'warning')
        return False
    return True

# ==================== INICIALIZACIÓN BASE DE DATOS ====================
def init_db():
    """Crea las tablas si no existen"""
    try:
        conn = get_connection()
        if conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS productos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    descripcion TEXT,
                    precio REAL NOT NULL,
                    stock INTEGER NOT NULL DEFAULT 0,
                    activo INTEGER NOT NULL DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME
                )
            """)

            conn.commit()
            conn.close()
            print("✅ Base de datos SQLite inicializada (usuarios + productos)")
    except Exception as e:
        print(f"Error inicializando base de datos: {e}")

# ==================== FUNCIÓN VERIFICAR reCAPTCHA ====================
def verificar_recaptcha(respuesta_recaptcha):
    try:
        data = {'secret': RECAPTCHA_SECRET_KEY, 'response': respuesta_recaptcha}
        respuesta = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data, timeout=5)
        return respuesta.json().get('success', False)
    except:
        return False

# ==================== RUTAS ====================
@app.route('/')
def inicio():
    return render_template('inicio.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id, nombre, password FROM usuarios WHERE email = ?', (email,))
            user = cursor.fetchone()
            conn.close()

            if user and check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['user_name'] = user[1]
                return redirect(url_for('dashboard'))
            else:
                flash('Email o contraseña incorrectos', 'danger')
        except Exception as e:
            flash('Error en el sistema', 'danger')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombre = request.form.get('nombre', '')
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        recaptcha_response = request.form.get('g-recaptcha-response', '')

        # 1) Validar reCAPTCHA
        if not verificar_recaptcha(recaptcha_response):
            flash('Por favor, completa el reCAPTCHA', 'danger')
            return redirect(url_for('register'))

        # 2) Validaciones backend
        errores = []

        # Nombre
        if not nombre or len(nombre.strip()) < 3:
            errores.append('El nombre debe tener al menos 3 letras reales.')
        elif not re.match(r"^[A-Za-zñÑáéíóúÁÉÍÓÚ\s]+$", nombre):
            errores.append('El nombre solo puede contener letras.')

        # Email
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_regex, email):
            errores.append('Ingresa un correo válido.')

        # Password: 8-20 + mayus + minus + num (sin símbolos)
        password_regex = r"^(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).{8,20}$"
        if not re.match(password_regex, password):
            errores.append('La contraseña debe tener: 8-20 caracteres, Mayúscula, Minúscula y Número.')

        if password != confirm_password:
            errores.append('Las contraseñas no coinciden.')

        if errores:
            for error in errores:
                flash(error, 'danger')
            return redirect(url_for('register'))

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT id FROM usuarios WHERE email = ?', (email,))
            if cursor.fetchone():
                conn.close()
                flash('Este correo ya está registrado', 'danger')
                return redirect(url_for('register'))

            hashed_pw = generate_password_hash(password)
            cursor.execute(
                'INSERT INTO usuarios (nombre, email, password) VALUES (?, ?, ?)',
                (nombre.strip(), email, hashed_pw)
            )
            conn.commit()
            new_id = cursor.lastrowid
            conn.close()

            session['user_id'] = new_id
            session['user_name'] = nombre.strip()

            flash(f'¡Bienvenido {nombre.strip()}! Cuenta creada.', 'success')
            return redirect(url_for('dashboard'))

        except Exception as e:
            flash(f'Error al registrar: {str(e)}', 'danger')

    return render_template('register.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Inicia sesión primero', 'warning')
        return redirect(url_for('login'))

    # Estadísticas de productos
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM productos")
        total_productos = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM productos WHERE activo = 1")
        productos_activos = cur.fetchone()[0]

        cur.execute("SELECT IFNULL(SUM(stock),0) FROM productos")
        total_stock = cur.fetchone()[0]

        conn.close()
    except:
        total_productos, productos_activos, total_stock = 0, 0, 0

    return render_template(
        'dashboard.html',
        nombre=session['user_name'],
        total_productos=total_productos,
        productos_activos=productos_activos,
        total_stock=total_stock
    )

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada', 'info')
    return redirect(url_for('inicio'))

# ==================== CRUD PRODUCTOS ====================

@app.route('/productos')
def productos_list():
    if not require_login():
        return redirect(url_for('login'))

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, nombre, descripcion, precio, stock, activo, created_at, updated_at
            FROM productos
            ORDER BY id DESC
        """)
        rows = cur.fetchall()
        conn.close()
        return render_template('productos.html', productos=rows, nombre=session.get('user_name', ''))
    except Exception as e:
        flash('Error cargando productos', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/productos/nuevo', methods=['GET', 'POST'])
def productos_nuevo():
    if not require_login():
        return redirect(url_for('login'))

    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        descripcion = request.form.get('descripcion', '').strip()
        precio = request.form.get('precio', '').strip()
        stock = request.form.get('stock', '').strip()
        activo = 1 if request.form.get('activo') == '1' else 0

        errores = []
        if not nombre or len(nombre) < 2:
            errores.append("El nombre es obligatorio (mínimo 2 caracteres).")

        try:
            precio_val = float(precio)
            if precio_val < 0:
                errores.append("El precio no puede ser negativo.")
        except:
            errores.append("Precio inválido.")

        try:
            stock_val = int(stock)
            if stock_val < 0:
                errores.append("El stock no puede ser negativo.")
        except:
            errores.append("Stock inválido.")

        if errores:
            for err in errores:
                flash(err, 'danger')
            return render_template('producto_form.html', modo='crear', producto=None, nombre=session.get('user_name', ''))

        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO productos (nombre, descripcion, precio, stock, activo, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                nombre,
                descripcion,
                precio_val,
                stock_val,
                activo,
                datetime.now().isoformat(sep=' ', timespec='seconds')
            ))
            conn.commit()
            conn.close()
            flash("Producto creado correctamente", "success")
            return redirect(url_for('productos_list'))
        except Exception as e:
            flash("Error al crear el producto", "danger")

    return render_template('producto_form.html', modo='crear', producto=None, nombre=session.get('user_name', ''))

@app.route('/productos/<int:producto_id>/editar', methods=['GET', 'POST'])
def productos_editar(producto_id):
    if not require_login():
        return redirect(url_for('login'))

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, nombre, descripcion, precio, stock, activo
            FROM productos
            WHERE id = ?
        """, (producto_id,))
        producto = cur.fetchone()

        if not producto:
            conn.close()
            flash("Producto no encontrado", "warning")
            return redirect(url_for('productos_list'))

        if request.method == 'POST':
            nombre = request.form.get('nombre', '').strip()
            descripcion = request.form.get('descripcion', '').strip()
            precio = request.form.get('precio', '').strip()
            stock = request.form.get('stock', '').strip()
            activo = 1 if request.form.get('activo') == '1' else 0

            errores = []
            if not nombre or len(nombre) < 2:
                errores.append("El nombre es obligatorio (mínimo 2 caracteres).")

            try:
                precio_val = float(precio)
                if precio_val < 0:
                    errores.append("El precio no puede ser negativo.")
            except:
                errores.append("Precio inválido.")

            try:
                stock_val = int(stock)
                if stock_val < 0:
                    errores.append("El stock no puede ser negativo.")
            except:
                errores.append("Stock inválido.")

            if errores:
                conn.close()
                for err in errores:
                    flash(err, 'danger')
                return render_template('producto_form.html', modo='editar', producto=producto, nombre=session.get('user_name', ''))

            cur.execute("""
                UPDATE productos
                SET nombre = ?, descripcion = ?, precio = ?, stock = ?, activo = ?, updated_at = ?
                WHERE id = ?
            """, (
                nombre,
                descripcion,
                precio_val,
                stock_val,
                activo,
                datetime.now().isoformat(sep=' ', timespec='seconds'),
                producto_id
            ))
            conn.commit()
            conn.close()

            flash("Producto actualizado correctamente", "success")
            return redirect(url_for('productos_list'))

        conn.close()
        return render_template('producto_form.html', modo='editar', producto=producto, nombre=session.get('user_name', ''))

    except Exception as e:
        flash("Error al editar el producto", "danger")
        return redirect(url_for('productos_list'))

@app.route('/productos/<int:producto_id>/eliminar', methods=['POST'])
def productos_eliminar(producto_id):
    if not require_login():
        return redirect(url_for('login'))

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM productos WHERE id = ?", (producto_id,))
        conn.commit()
        conn.close()
        flash("Producto eliminado", "info")
    except Exception as e:
        flash("Error al eliminar producto", "danger")

    return redirect(url_for('productos_list'))


if __name__ == '__main__':
    if not os.path.exists('templates'):
        os.makedirs('templates')

    init_db()
    app.run(debug=True, port=5000)