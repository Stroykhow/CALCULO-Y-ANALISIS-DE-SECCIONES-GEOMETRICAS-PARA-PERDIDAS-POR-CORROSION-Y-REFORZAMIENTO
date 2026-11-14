"""Pruebas del modelo contra casos resueltos a mano y contra pysections."""

import numpy as np
import pytest

from app import modelo
from app.sections import BulbTeeGirderBridge
from app.validacion import leer_numero

LOSA_IDEAL = dict(width=2.00, thickness=0.25)
LOSA_MOD = dict(width=1.80, thickness=0.25)


def test_rectangulo_resuelto_a_mano():
    """Rectángulo b = 2.00 m, h = 0.25 m.

    A = b·h = 0.5 m²;  yc = h/2 = 0.125 m;  Ixx = b·h³/12 = 2.6042e-3 m⁴;
    Iyy = h·b³/12 = 0.16667 m⁴;  Zx = b·h²/6 = 2.0833e-2 m³.
    """
    p = modelo.propiedades("rectangular", LOSA_IDEAL)
    assert p["area"] == pytest.approx(0.5)
    assert p["yc"] == pytest.approx(0.125)
    assert p["xc"] == pytest.approx(0.0, abs=1e-12)
    assert p["ixx"] == pytest.approx(2.0 * 0.25**3 / 12)
    assert p["iyy"] == pytest.approx(0.25 * 2.0**3 / 12)
    assert p["ixy"] == pytest.approx(0.0, abs=1e-12)
    assert p["zx_crit"] == pytest.approx(2.0 * 0.25**2 / 6)


def test_triangulo_resuelto_a_mano():
    """Triángulo rectángulo b = 3, h = 2 (vértices (0,0), (3,0), (0,2)).

    A = 3 m²; centroide (1, 2/3); Ixx = b·h³/36 = 2/3 m⁴; Iyy = h·b³/36 = 1.5 m⁴;
    Ixy = −b²·h²/72 = −0.5 m⁴.
    """
    p = modelo.propiedades_lote(np.array([[0, 0], [3, 0], [0, 2]]), 2.0)
    assert p["area"][0] == pytest.approx(3.0)
    assert p["xc"][0] == pytest.approx(1.0)
    assert p["yc"][0] == pytest.approx(2 / 3)
    assert p["ixx"][0] == pytest.approx(2 / 3)
    assert p["iyy"][0] == pytest.approx(1.5)
    assert p["ixy"][0] == pytest.approx(-0.5)


def test_sentido_de_recorrido_no_cambia_el_resultado():
    puntos = np.array([[0, 0], [3, 0], [0, 2]], dtype=float)
    horario = modelo.propiedades_lote(puntos[::-1], 2.0)
    antihorario = modelo.propiedades_lote(puntos, 2.0)
    for clave in antihorario:
        assert horario[clave][0] == pytest.approx(antihorario[clave][0])


def test_bulb_tee_coincide_con_pysections():
    """El cálculo vectorizado reproduce los resultados de la librería del curso."""
    p = modelo.EJEMPLO["ideal"]
    referencia = BulbTeeGirderBridge(**p)
    r = modelo.propiedades("bulb_tee", p)
    assert r["area"] == pytest.approx(referencia.area)
    assert r["yc"] == pytest.approx(referencia.z)
    assert r["ixx"] == pytest.approx(referencia.Iyy)
    assert r["iyy"] == pytest.approx(referencia.Izz)
    assert r["zx_inf"] == pytest.approx(referencia.wi)
    assert r["zx_sup"] == pytest.approx(referencia.ws)


def test_perdida_de_10_por_ciento_es_naranja():
    """Reducir el ancho de 2.00 a 1.80 m reduce A, Ixx y Zx exactamente 10 %."""
    r = modelo.comparar("rectangular", LOSA_IDEAL, LOSA_MOD)
    assert r.perdida_area == pytest.approx(10.0)
    assert r.perdida_ixx == pytest.approx(10.0)
    assert r.perdida_zx == pytest.approx(10.0)
    assert r.severidad == "NARANJA"
    assert not r.cumple


@pytest.mark.parametrize("perdida, severidad", [
    (0.0, "VERDE"), (9.99, "VERDE"), (10.0, "NARANJA"), (25.0, "NARANJA"),
    (25.01, "ROJO"), (-15.0, "VERDE"),
])
def test_clasificacion_por_umbrales(perdida, severidad):
    assert modelo.clasificar(perdida)[0] == severidad


def test_brentq_encuentra_los_umbrales_del_rectangulo():
    """Zx ∝ b. Con b(α) = 2.0 − 0.2·α: Zx pierde 10 % en α = 1 y 25 % en α = 2.5.

    Con edad de 20 años en la inspección, los umbrales ocurren a los 20 y 50 años.
    """
    r = modelo.comparar("rectangular", LOSA_IDEAL, LOSA_MOD, edad_anios=20)
    proy = r.proyeccion
    assert proy.alfa_umbral[10.0] == pytest.approx(1.0, abs=1e-8)
    assert proy.alfa_umbral[25.0] == pytest.approx(2.5, abs=1e-8)
    assert proy.tiempo_umbral(10.0) == pytest.approx(20.0, abs=1e-6)
    assert proy.tiempo_umbral(25.0) == pytest.approx(50.0, abs=1e-6)


def test_malla_vectorizada_coincide_con_calculo_individual():
    r = modelo.comparar("bulb_tee", modelo.EJEMPLO["ideal"], modelo.EJEMPLO["modificada"])
    proy = r.proyeccion
    i = int(np.argmin(np.abs(proy.alfa - 1.0)))
    a = proy.alfa[i]
    p = {k: modelo.EJEMPLO["ideal"][k] + a * (modelo.EJEMPLO["modificada"][k]
                                              - modelo.EJEMPLO["ideal"][k])
         for k in modelo.EJEMPLO["ideal"]}
    individual = modelo.propiedades("bulb_tee", p)["zx_crit"] / r.ideal["zx_crit"] * 100
    assert proy.capacidad_zx[i] == pytest.approx(individual)


def test_reforzamiento_no_alcanza_umbrales():
    r = modelo.comparar("rectangular", LOSA_IDEAL, dict(width=2.0, thickness=0.30))
    assert r.perdida_zx < 0
    assert r.severidad == "VERDE"
    assert r.proyeccion.alfa_umbral == {10.0: None, 25.0: None}


@pytest.mark.parametrize("parametros", [
    dict(width=-1.0, thickness=0.25),
    dict(width=0.0, thickness=0.25),
    dict(width=2.0),
])
def test_parametros_invalidos_lanzan_error(parametros):
    with pytest.raises(ValueError):
        modelo.comparar("rectangular", parametros, LOSA_MOD)


def test_bulb_tee_con_alturas_incompatibles():
    p = dict(modelo.EJEMPLO["ideal"], d1=0.40)
    with pytest.raises(ValueError, match="altura total"):
        modelo.validar_parametros("bulb_tee", p)


@pytest.mark.parametrize("texto, valor, error", [
    ("2,5", 2.5, None), (" 0.25 ", 0.25, None), ("", None, "Campo obligatorio"),
    ("abc", None, "Debe ser un número"), ("-3", None, "Debe ser mayor que 0"),
    ("nan", None, "Debe ser un número finito"),
])
def test_lectura_de_campos(texto, valor, error):
    assert leer_numero(texto) == (valor, error)


def test_campo_opcional_vacio():
    assert leer_numero("", obligatorio=False) == (None, None)
