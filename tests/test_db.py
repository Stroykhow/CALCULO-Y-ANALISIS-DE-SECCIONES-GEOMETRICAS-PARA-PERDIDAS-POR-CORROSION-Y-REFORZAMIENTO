"""Pruebas de la capa SQLite con una base de datos temporal."""

import pytest

from app import db, modelo


@pytest.fixture
def conexion(tmp_path):
    con = db.conectar(tmp_path / "prueba.db")
    yield con
    con.close()


@pytest.fixture
def resultado():
    return modelo.comparar("rectangular", dict(width=2.0, thickness=0.25),
                           dict(width=1.8, thickness=0.25), 20)


def test_crea_tablas_si_no_existen(tmp_path):
    con = db.conectar(tmp_path / "nueva" / "datos.db")
    tablas = {f[0] for f in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"proyectos", "calculos"} <= tablas


def test_guardar_listar_reabrir_y_eliminar(conexion, resultado):
    i = db.guardar_calculo(conexion, "Puente A", "Losa luz 1", resultado, 20)
    db.guardar_calculo(conexion, "Puente B", "Losa luz 2", resultado)
    assert len(db.listar_calculos(conexion)) == 2
    assert [c["nombre"] for c in db.listar_calculos(conexion, "Puente A")] == ["Losa luz 1"]

    calculo = db.obtener_calculo(conexion, i)
    assert calculo["param_ideal"] == {"width": 2.0, "thickness": 0.25}
    assert calculo["severidad"] == "NARANJA"
    reabierto = modelo.comparar(calculo["tipo_seccion"], calculo["param_ideal"],
                                calculo["param_mod"], calculo["edad_anios"])
    assert reabierto.perdida_zx == pytest.approx(resultado.perdida_zx)

    assert db.eliminar_calculo(conexion, i)
    assert db.obtener_calculo(conexion, i) is None
    assert [p["nombre"] for p in db.listar_proyectos(conexion)] == ["Puente B"]


def test_busqueda_es_parametrizada(conexion, resultado):
    db.guardar_calculo(conexion, "Puente A", "Losa", resultado)
    assert db.listar_calculos(conexion, "' OR 1=1 --") == []


def test_llave_foranea_activa(conexion):
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        conexion.execute(
            "INSERT INTO calculos (proyecto_id, nombre, tipo_seccion, param_ideal, param_mod,"
            " area_ideal, area_mod, zx_ideal, zx_mod, perdida_zx, severidad, dictamen, creado)"
            " VALUES (999, 'x', 'rectangular', '{}', '{}', 1, 1, 1, 1, 0, 'VERDE', '', '')")


def test_guarda_y_reabre_la_flexion_con_sus_capas(conexion):
    from app import flexion as fx
    from app import modelo
    e = modelo.EJEMPLO
    r = modelo.comparar(e["tipo"], e["ideal"], e["modificada"], e["edad_anios"], fx.EJEMPLO)
    i = db.guardar_calculo(conexion, "Puente A", "Viga 1", r, e["edad_anios"])

    calculo = db.obtener_calculo(conexion, i)
    assert calculo["phi_mn_mod"] == pytest.approx(r.flexion.modificada.phi_mn)
    assert calculo["cumple_flexion"] == int(r.flexion.modificada.cumple)
    datos = fx.DatosFlexion.desde_diccionario(calculo["datos_flexion"], calculo["capas"])
    assert datos == fx.EJEMPLO

    db.eliminar_calculo(conexion, i)                 # las capas se borran en cascada
    assert conexion.execute("SELECT COUNT(*) FROM capas_acero").fetchone()[0] == 0


def test_calculo_sin_flexion_no_tiene_capas(conexion, resultado):
    i = db.guardar_calculo(conexion, "Puente A", "Losa", resultado)
    calculo = db.obtener_calculo(conexion, i)
    assert calculo["capas"] == [] and calculo["datos_flexion"] is None


def test_migra_una_base_de_la_version_anterior(tmp_path):
    """Una base creada sin las columnas de flexión se actualiza al conectar."""
    import sqlite3
    ruta = tmp_path / "vieja.db"
    vieja = sqlite3.connect(ruta)
    vieja.executescript("""
        CREATE TABLE proyectos (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE,
                                descripcion TEXT DEFAULT '', creado TEXT NOT NULL);
        CREATE TABLE calculos (id INTEGER PRIMARY KEY, proyecto_id INTEGER NOT NULL,
            nombre TEXT NOT NULL, tipo_seccion TEXT NOT NULL, param_ideal TEXT NOT NULL,
            param_mod TEXT NOT NULL, edad_anios REAL, area_ideal REAL NOT NULL,
            area_mod REAL NOT NULL, zx_ideal REAL NOT NULL, zx_mod REAL NOT NULL,
            perdida_zx REAL NOT NULL, severidad TEXT NOT NULL, dictamen TEXT NOT NULL,
            creado TEXT NOT NULL);
    """)
    vieja.close()
    con = db.conectar(ruta)
    columnas = {f["name"] for f in con.execute("PRAGMA table_info(calculos)")}
    assert {"datos_flexion", "mu", "phi_mn_mod", "cumple_flexion"} <= columnas
    con.close()


def test_guarda_y_reabre_las_estaciones(conexion):
    from app import estaciones as est
    from app import flexion as fx
    from app import modelo
    e = modelo.EJEMPLO
    revision = (est.EJEMPLO_ESTRIBOS, est.ejemplo_estaciones())
    r = modelo.comparar(e["tipo"], e["ideal"], e["modificada"], e["edad_anios"], fx.EJEMPLO,
                        revision)
    i = db.guardar_calculo(conexion, "Puente A", "Viga 1", r, e["edad_anios"])
    calculo = db.obtener_calculo(conexion, i)
    assert calculo["x_critico"] == pytest.approx(1.0)
    assert calculo["cumple_estaciones"] == 0
    assert est.estribos_desde_diccionario(calculo["datos_estribos"]) == est.EJEMPLO_ESTRIBOS
    assert est.estaciones_desde_filas(calculo["estaciones"]) == revision[1]
    db.eliminar_calculo(conexion, i)
    assert conexion.execute("SELECT COUNT(*) FROM estaciones").fetchone()[0] == 0
