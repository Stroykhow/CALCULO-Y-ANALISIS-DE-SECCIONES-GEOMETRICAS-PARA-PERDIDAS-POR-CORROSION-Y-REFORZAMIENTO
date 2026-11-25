"""Pruebas del análisis a flexión contra casos resueltos a mano (NSR-10)."""

import math

import numpy as np
import pytest

from app import flexion as fx
from app import modelo

VIGA = dict(width=0.30, thickness=0.50)          # viga rectangular 30 × 50 cm


def _datos(**cambios):
    base = dict(fc=28.0, fy=420.0, capas=[fx.Capa(3, 20.0, 0.06)], luz=6.0,
                carga_muerta=10.0, carga_viva=8.0)
    base.update(cambios)
    return fx.DatosFlexion(**base)


def test_viga_rectangular_resuelta_a_mano():
    """Viga 30 × 50 cm, 3 barras de 20 mm con d = 44 cm, f'c = 28 MPa, fy = 420 MPa.

    As = 942.5 mm²;  a = As·fy / (0.85·f'c·b) = 55.44 mm;  c = a / 0.85 = 65.22 mm
    Mn = As·fy·(d − a/2) = 163.20 kN·m;  εt = 0.003·(440 − 65.2)/65.2 = 0.0172 → φ = 0.90
    Mcr = 0.62·√28 · (b·h³/12) / (h/2) = 41.01 kN·m
    """
    r = fx.evaluar_flexion("rectangular", VIGA, _datos())
    As = 3 * math.pi * 20**2 / 4
    a = As * 420 / (0.85 * 28 * 300)
    assert r.as_total_mm2 == pytest.approx(As)
    assert r.a * 1000 == pytest.approx(a)
    assert r.c * 1000 == pytest.approx(a / 0.85)
    assert r.mn == pytest.approx(As * 420 * (440 - a / 2) / 1e6)
    assert r.phi == pytest.approx(0.90)
    assert r.eps_t == pytest.approx(0.003 * (440 - a / 0.85) / (a / 0.85))
    assert r.mcr == pytest.approx(0.62 * math.sqrt(28) * 0.30 * 0.5**3 / 12 / 0.25 * 1000)
    assert all(capa["fluye"] for capa in r.capas)


def test_carga_ultima_y_peso_propio():
    """Peso propio = 24 × 0.15 = 3.6 kN/m;  wu = 1.2(3.6 + 10) + 1.6·8 = 29.12 kN/m;  Mu = wu·6²/8."""
    r = fx.evaluar_flexion("rectangular", VIGA, _datos())
    assert r.peso_propio == pytest.approx(3.6)
    assert r.wu == pytest.approx(1.2 * 13.6 + 1.6 * 8)
    assert r.mu == pytest.approx(r.wu * 36 / 8)
    assert r.cumple == (r.phi_mn >= r.mu)


def test_combinacion_14D_cuando_no_hay_carga_viva():
    wu, mu = fx.momento_ultimo(10.0, 20.0, 0.0)
    assert wu == pytest.approx(28.0)
    assert mu == pytest.approx(28.0 * 100 / 8)


@pytest.mark.parametrize("fc, esperado", [(21, 0.85), (28, 0.85), (35, 0.80), (56, 0.65), (70, 0.65)])
def test_beta1(fc, esperado):
    assert fx.beta1(fc) == pytest.approx(esperado)


@pytest.mark.parametrize("eps_t, esperado", [(0.010, 0.90), (0.005, 0.90), (0.0021, 0.65),
                                             (0.0001, 0.65), (0.0035, 0.65 + 0.25 * 1.4 / 2.9)])
def test_factor_phi(eps_t, esperado):
    assert fx.factor_phi(eps_t, 420 / 200_000) == pytest.approx(esperado)


def test_corrosion_del_acero_reduce_la_resistencia():
    """Con 20 % menos de acero, Mn baja un poco menos de 20 %, porque el bloque a
    se achica y el brazo d − a/2 crece: Mn' / Mn = 0.8·(440 − 0.8·a/2) / (440 − a/2)."""
    sana = fx.evaluar_flexion("rectangular", VIGA, _datos())
    corroida = fx.evaluar_flexion("rectangular", VIGA, _datos(), factor_acero=0.8)
    assert corroida.as_total_mm2 == pytest.approx(0.8 * sana.as_total_mm2)
    a = sana.a * 1000
    assert corroida.mn / sana.mn == pytest.approx(0.8 * (440 - 0.8 * a / 2) / (440 - a / 2))


def test_bulb_tee_con_bloque_en_la_aleta_superior():
    """Si a cabe en la aleta superior (d2 = 7.5 cm), la Bulb-Tee trabaja como un
    rectángulo de ancho b1: Mn = T·(d − a/2), con a = T / (0.85·f'c·b1)."""
    datos = fx.EJEMPLO
    r = fx.evaluar_flexion("bulb_tee", modelo.EJEMPLO["ideal"], datos)
    b1 = modelo.EJEMPLO["ideal"]["b1"]
    T = sum(c.area_mm2 for c in datos.capas) * 1e-6 * datos.fy        # MN
    a = T / (0.85 * datos.fc * b1)
    assert a < modelo.EJEMPLO["ideal"]["d2"]
    assert r.a == pytest.approx(a)
    d = 1.60 - np.mean([c.y for c in datos.capas])
    assert r.mn == pytest.approx(T * (d - a / 2) * 1000)


def test_recorte_de_la_zona_comprimida():
    cuadrado = np.array([[0, 0], [2, 0], [2, 2], [0, 2]], dtype=float)
    zona = fx.recortar_arriba(cuadrado, 1.5)
    assert modelo.propiedades_lote(zona, 2.0)["area"][0] == pytest.approx(1.0)


@pytest.mark.parametrize("y0", [0.0, 0.05, 0.38, 0.9, 1.45, 1.55])
def test_recorte_bulb_tee_contra_integracion_del_ancho(y0):
    """El área recortada coincide con sumar el ancho b(y) de la viga en unas 20 000 franjas
    (regla del punto medio), una referencia independiente del recorte del polígono."""
    p = modelo.EJEMPLO["ideal"]
    puntos = modelo.construir_seccion("bulb_tee", p).points
    zona = fx.recortar_arriba(puntos, y0)

    bordes = np.linspace(y0, p["d1"], 19_998)   # 19 997 franjas: ningún punto medio cae
    #                                             justo en la altura de un vértice
    ys = (bordes[:-1] + bordes[1:]) / 2                    # puntos medios de las franjas
    A, B = puntos, np.roll(puntos, -1, axis=0)
    y = ys[:, np.newaxis]                                  # (franjas, 1) frente a (1, lados)
    cruza = (A[:, 1] - y) * (B[:, 1] - y) < 0
    with np.errstate(divide="ignore", invalid="ignore"):
        x = A[:, 0] + (y - A[:, 1]) / (B[:, 1] - A[:, 1]) * (B[:, 0] - A[:, 0])
    ancho = np.where(cruza, x, -np.inf).max(axis=1) - np.where(cruza, x, np.inf).min(axis=1)
    area_ref = (ancho * np.diff(bordes)).sum()
    assert modelo.propiedades_lote(zona, p["d1"])["area"][0] == pytest.approx(area_ref, rel=1e-4)


def test_comparacion_y_proyeccion_del_ejemplo():
    e = modelo.EJEMPLO
    r = modelo.comparar(e["tipo"], e["ideal"], e["modificada"], e["edad_anios"], fx.EJEMPLO)
    f = r.flexion
    assert f.ideal.cumple and f.modificada.phi_mn < f.ideal.phi_mn
    assert f.perdida_phi_mn > 0
    assert f.alfa_falla is not None and f.alfa_falla > 1        # todavía cumple hoy
    assert f.tiempo_falla == pytest.approx(f.alfa_falla * e["edad_anios"])


def test_viga_que_no_cumple_desde_el_diseno():
    datos = _datos(luz=12.0)
    r = modelo.comparar("rectangular", VIGA, VIGA, 10, datos)
    assert not r.flexion.ideal.cumple
    assert r.flexion.alfa_falla == 0.0


@pytest.mark.parametrize("cambios, mensaje", [
    (dict(capas=[]), "al menos una capa"),
    (dict(capas=[fx.Capa(3, 20.0, 0.60)]), "fuera de la sección"),
    (dict(fc=0.0), "mayores que cero"),
    (dict(perdida_acero=100.0), "entre 0 %"),
    (dict(luz=-1.0), "luz"),
])
def test_datos_invalidos(cambios, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        fx.evaluar_flexion("rectangular", VIGA, _datos(**cambios))


def test_viga_sobrerreforzada_no_es_ductil():
    """Con mucho acero, el acero no fluye: εt < εy → φ = 0.65 y no cumple εt ≥ 0.004."""
    r = fx.evaluar_flexion("rectangular", VIGA, _datos(capas=[fx.Capa(10, 32.3, 0.06)]))
    assert r.eps_t < r.eps_y
    assert r.phi == pytest.approx(0.65)
    assert not r.ductil and not r.capas[0]["fluye"]


def test_datos_ida_y_vuelta_a_diccionario():
    datos = fx.EJEMPLO
    capas = [dict(n_barras=c.n_barras, diametro_mm=c.diametro_mm, y=c.y) for c in datos.capas]
    copia = fx.DatosFlexion.desde_diccionario(datos.a_diccionario(), capas)
    assert copia == datos
