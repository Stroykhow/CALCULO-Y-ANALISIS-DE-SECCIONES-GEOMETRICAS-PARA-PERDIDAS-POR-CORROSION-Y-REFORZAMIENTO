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
