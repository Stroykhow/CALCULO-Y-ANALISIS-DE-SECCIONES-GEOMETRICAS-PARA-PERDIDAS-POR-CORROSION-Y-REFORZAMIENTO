"""Persistencia en SQLite: proyectos y cálculos.

Todo el SQL del programa vive en este módulo y usa consultas parametrizadas (?).
La base de datos se crea sola la primera vez (CREATE TABLE IF NOT EXISTS).

Esquema
-------
proyectos (1) ──< calculos (N) ──< capas_acero (N)
    calculos.proyecto_id   → proyectos.id
    capas_acero.calculo_id → calculos.id

Las bases creadas con versiones anteriores se actualizan solas: ``conectar``
agrega las columnas de flexión que falten (ALTER TABLE ... ADD COLUMN).
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

RUTA_POR_DEFECTO = Path(__file__).resolve().parent.parent / "datos" / "proyectos.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS proyectos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT    NOT NULL UNIQUE,
    descripcion TEXT    DEFAULT '',
    creado      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS calculos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id     INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    nombre          TEXT    NOT NULL,
    tipo_seccion    TEXT    NOT NULL,
    param_ideal     TEXT    NOT NULL,   -- JSON con las cotas (m)
    param_mod       TEXT    NOT NULL,   -- JSON con las cotas (m)
    edad_anios      REAL,
    area_ideal      REAL    NOT NULL,   -- m²
    area_mod        REAL    NOT NULL,   -- m²
    zx_ideal        REAL    NOT NULL,   -- m³
    zx_mod          REAL    NOT NULL,   -- m³
    perdida_zx      REAL    NOT NULL,   -- %
    severidad       TEXT    NOT NULL,
    dictamen        TEXT    NOT NULL,
    creado          TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_calculos_proyecto ON calculos(proyecto_id);

CREATE TABLE IF NOT EXISTS capas_acero (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    calculo_id   INTEGER NOT NULL REFERENCES calculos(id) ON DELETE CASCADE,
    orden        INTEGER NOT NULL,
    n_barras     INTEGER NOT NULL,
    diametro_mm  REAL    NOT NULL,
    y_m          REAL    NOT NULL       -- altura del centro de las barras desde la base
);

CREATE INDEX IF NOT EXISTS idx_capas_calculo ON capas_acero(calculo_id);
"""

# Columnas de flexión agregadas en la versión 2 (nombre, tipo SQL)
COLUMNAS_FLEXION = [
    ("datos_flexion", "TEXT"),         # JSON: f'c, fy, luz, cargas, pérdida de acero
    ("mu", "REAL"),                    # kN·m
    ("phi_mn_ideal", "REAL"),          # kN·m
    ("phi_mn_mod", "REAL"),            # kN·m
    ("cumple_flexion", "INTEGER"),     # 1 / 0 para la sección modificada
]


def conectar(ruta=None):
    """Abre la base de datos (creándola si no existe) y devuelve la conexión."""
    ruta = Path(ruta) if ruta else RUTA_POR_DEFECTO
    if str(ruta) != ":memory:":
        ruta.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(ruta)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    conexion.executescript(ESQUEMA)
    _migrar(conexion)
    return conexion


def _migrar(conexion):
    """Agrega a ``calculos`` las columnas de flexión que no existan todavía."""
    existentes = {fila["name"] for fila in conexion.execute("PRAGMA table_info(calculos)")}
    for nombre, tipo in COLUMNAS_FLEXION:
        if nombre not in existentes:
            # nombre y tipo vienen de la constante de arriba, nunca del usuario
            conexion.execute(f"ALTER TABLE calculos ADD COLUMN {nombre} {tipo}")
    conexion.commit()


def _ahora():
    return datetime.now().isoformat(timespec="seconds")


def obtener_o_crear_proyecto(conexion, nombre, descripcion=""):
    """Devuelve el id del proyecto con ese nombre; lo crea si no existe."""
    nombre = nombre.strip()
    if not nombre:
        raise ValueError("El nombre del proyecto es obligatorio")
    fila = conexion.execute("SELECT id FROM proyectos WHERE nombre = ?", (nombre,)).fetchone()
    if fila:
        return fila["id"]
    cursor = conexion.execute(
        "INSERT INTO proyectos (nombre, descripcion, creado) VALUES (?, ?, ?)",
        (nombre, descripcion, _ahora()),
    )
    conexion.commit()
    return cursor.lastrowid


def guardar_calculo(conexion, proyecto, nombre, resultado, edad_anios=None):
    """Guarda un ``modelo.Resultado`` dentro del proyecto indicado. Devuelve el id."""
    nombre = nombre.strip()
    if not nombre:
        raise ValueError("El nombre del cálculo es obligatorio")
    proyecto_id = obtener_o_crear_proyecto(conexion, proyecto)
    flex = resultado.flexion
    cursor = conexion.execute(
        """INSERT INTO calculos (proyecto_id, nombre, tipo_seccion, param_ideal, param_mod,
               edad_anios, area_ideal, area_mod, zx_ideal, zx_mod, perdida_zx,
               severidad, dictamen, creado, datos_flexion, mu, phi_mn_ideal, phi_mn_mod,
               cumple_flexion)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            proyecto_id, nombre, resultado.tipo,
            json.dumps(resultado.ideal_param), json.dumps(resultado.mod_param),
            edad_anios,
            resultado.ideal["area"], resultado.modificada["area"],
            resultado.ideal["zx_crit"], resultado.modificada["zx_crit"],
            resultado.perdida_zx, resultado.severidad, resultado.dictamen, _ahora(),
            json.dumps(flex.datos.a_diccionario()) if flex else None,
            flex.modificada.mu if flex else None,
            flex.ideal.phi_mn if flex else None,
            flex.modificada.phi_mn if flex else None,
            int(flex.modificada.cumple) if flex else None,
        ),
    )
    calculo_id = cursor.lastrowid
    if flex:
        conexion.executemany(
            """INSERT INTO capas_acero (calculo_id, orden, n_barras, diametro_mm, y_m)
               VALUES (?, ?, ?, ?, ?)""",
            [(calculo_id, i, c.n_barras, c.diametro_mm, c.y)
             for i, c in enumerate(flex.datos.capas)],
        )
    conexion.commit()
    return calculo_id


def _a_diccionario(fila):
    datos = dict(fila)
    for clave in ("param_ideal", "param_mod", "datos_flexion"):
        if datos.get(clave):
            datos[clave] = json.loads(datos[clave])
    return datos


def listar_capas(conexion, calculo_id):
    """Capas de acero de un cálculo, en el orden en que se ingresaron."""
    filas = conexion.execute(
        """SELECT n_barras, diametro_mm, y_m AS y FROM capas_acero
           WHERE calculo_id = ? ORDER BY orden""",
        (calculo_id,),
    ).fetchall()
    return [dict(f) for f in filas]


def listar_calculos(conexion, filtro=""):
    """Lista los cálculos (más recientes primero), filtrando por proyecto o nombre."""
    patron = f"%{filtro.strip()}%"
    filas = conexion.execute(
        """SELECT c.*, p.nombre AS proyecto
           FROM calculos c JOIN proyectos p ON p.id = c.proyecto_id
           WHERE p.nombre LIKE ? OR c.nombre LIKE ? OR c.severidad LIKE ?
           ORDER BY c.id DESC""",
        (patron, patron, patron),
    ).fetchall()
    return [_a_diccionario(f) for f in filas]


def obtener_calculo(conexion, calculo_id):
    """Devuelve un cálculo completo (con sus parámetros) o None si no existe."""
    fila = conexion.execute(
        """SELECT c.*, p.nombre AS proyecto
           FROM calculos c JOIN proyectos p ON p.id = c.proyecto_id
           WHERE c.id = ?""",
        (calculo_id,),
    ).fetchone()
    if not fila:
        return None
    calculo = _a_diccionario(fila)
    calculo["capas"] = listar_capas(conexion, calculo_id)
    return calculo


def eliminar_calculo(conexion, calculo_id):
    """Elimina un cálculo. Si su proyecto queda vacío, también se elimina."""
    fila = conexion.execute("SELECT proyecto_id FROM calculos WHERE id = ?",
                            (calculo_id,)).fetchone()
    if not fila:
        return False
    conexion.execute("DELETE FROM calculos WHERE id = ?", (calculo_id,))
    conexion.execute(
        "DELETE FROM proyectos WHERE id = ? AND NOT EXISTS "
        "(SELECT 1 FROM calculos WHERE proyecto_id = ?)",
        (fila["proyecto_id"], fila["proyecto_id"]),
    )
    conexion.commit()
    return True


def listar_proyectos(conexion):
    """Proyectos con el número de cálculos de cada uno."""
    filas = conexion.execute(
        """SELECT p.id, p.nombre, p.creado, COUNT(c.id) AS n_calculos
           FROM proyectos p LEFT JOIN calculos c ON c.proyecto_id = p.id
           GROUP BY p.id ORDER BY p.nombre"""
    ).fetchall()
    return [dict(f) for f in filas]
