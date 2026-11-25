"""Pruebas de la revisión por estaciones (flexión y cortante, NSR-10)."""

import math

import numpy as np
import pytest

from app import estaciones as est
from app import flexion as fx
from app import modelo

VIGA = dict(width=0.30, thickness=0.50)
DATOS = fx.DatosFlexion(fc=28.0, fy=420.0, capas=[fx.Capa(3, 20.0, 0.06)], luz=6.0,
                        carga_muerta=10.0, carga_viva=8.0)
ESTRIBOS = est.Estribos(diametro_mm=9.5, ramas=2, separacion=0.15, fyt=420.0)


def test_demanda_de_viga_simplemente_apoyada():
    """wu = 29.12 kN/m, L = 6 m:  Mu(1.5) = wu·1.5·4.5/2,  Vu(1.5) = wu·(3 − 1.5)."""
    mu, vu = est.demanda([0.0, 1.5, 3.0, 6.0], 29.12, 6.0)
    assert mu == pytest.approx([0.0, 29.12 * 1.5 * 4.5 / 2, 29.12 * 9 / 2, 0.0])
    assert vu == pytest.approx([29.12 * 3, 29.12 * 1.5, 0.0, 29.12 * 3])


def test_cortante_resuelto_a_mano():
    """Viga 30 × 50 cm, d = 44 cm, f'c = 28 MPa, estribos Ø9.5 de 2 ramas cada 15 cm, fyt = 420.

    Vc = 0.17·√28·0.30·0.44 = 118.74 kN;  Av = 141.76 mm²;
    Vs = Av·fyt·d/s = 174.65 kN;  φVn = 0.75·(Vc + Vs) = 220.04 kN
    """
    phi_vn, vc, vs = est.resistencia_cortante(28.0, 0.30, 0.44, ESTRIBOS)
    av = 2 * math.pi * 9.5**2 / 4
    assert vc == pytest.approx(0.17 * math.sqrt(28) * 0.30 * 0.44 * 1000)
    assert vs == pytest.approx(av * 1e-6 * 420 * 0.44 / 0.15 * 1000)
    assert phi_vn == pytest.approx(0.75 * (vc + vs))
    assert float(phi_vn) == pytest.approx(220.04, abs=0.01)


def test_limite_de_vs():
    """Con estribos muy cerrados, Vs no pasa de 0.66·√f'c·bw·d (NSR-10 C.11.4.7.9)."""
    cerrados = est.Estribos(12.7, 4, 0.03)
    _, _, vs = est.resistencia_cortante(28.0, 0.30, 0.44, cerrados)
    assert float(vs) == pytest.approx(0.66 * math.sqrt(28) * 0.30 * 0.44 * 1000)


def test_estribos_corroidos_reducen_vs():
    _, _, vs_sano = est.resistencia_cortante(28.0, 0.30, 0.44, ESTRIBOS, 1.0)
    _, _, vs_corr = est.resistencia_cortante(28.0, 0.30, 0.44, ESTRIBOS, 0.6)
    assert float(vs_corr) == pytest.approx(0.6 * float(vs_sano))


def test_generar_estaciones_incluye_los_apoyos():
    xs = [e.x for e in est.generar_estaciones(6.5, 1.0)]
    assert xs[0] == 0.0 and xs[-1] == 6.5 and len(xs) == 8


def test_estacion_sana_coincide_con_flexion_y_cortante_sueltos():
    """En una viga sin daño, cada estación usa el mismo φMn y φVn de la sección sana."""
    r = est.evaluar_estaciones("rectangular", VIGA, VIGA, DATOS, ESTRIBOS,
                               est.generar_estaciones(6.0, 1.5))
    sana = fx.evaluar_flexion("rectangular", VIGA, DATOS)
    assert r.phi_mn == pytest.approx(sana.phi_mn)
    phi_vn, _, _ = est.resistencia_cortante(28.0, 0.30, sana.d_efectivo, ESTRIBOS)
    assert r.phi_vn == pytest.approx(float(phi_vn))
    assert r.mu.max() == pytest.approx(sana.mu)            # Mu máximo en el centro
    assert r.cumple_todo


def test_ejemplo_falla_por_cortante_en_la_junta():
    e = modelo.EJEMPLO
    r = est.evaluar_estaciones(e["tipo"], e["ideal"], e["modificada"], fx.EJEMPLO,
                               est.EJEMPLO_ESTRIBOS, est.ejemplo_estaciones())
    i = r.indice_critico
    assert r.x[i] == pytest.approx(1.0)
    assert r.relacion_v[i] > r.relacion_m[i] > 0
    assert not r.cumple_todo
    assert "controla cortante" in r.resumen()


def test_estaciones_se_ordenan_por_x():
    desordenadas = [est.Estacion(3.0), est.Estacion(0.0), est.Estacion(6.0)]
    r = est.evaluar_estaciones("rectangular", VIGA, VIGA, DATOS, ESTRIBOS, desordenadas)
    assert list(r.x) == [0.0, 3.0, 6.0]


@pytest.mark.parametrize("estaciones, mensaje", [
    ([], "al menos una"),
    ([est.Estacion(7.0)], "fuera de la viga"),
    ([est.Estacion(1.0, perdida_estribos=100.0)], "entre 0 %"),
])
def test_estaciones_invalidas(estaciones, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        est.evaluar_estaciones("rectangular", VIGA, VIGA, DATOS, ESTRIBOS, estaciones)


def test_estribos_ida_y_vuelta():
    copia = est.estribos_desde_diccionario(est.estribos_a_diccionario(est.EJEMPLO_ESTRIBOS))
    assert copia == est.EJEMPLO_ESTRIBOS
    filas = [dict(x=1.0, danada=1, perdida_acero=10.0, perdida_estribos=5.0)]
    assert est.estaciones_desde_filas(filas) == [est.Estacion(1.0, True, 10.0, 5.0)]
    assert np.isclose(est.Estribos(9.5, 2, 0.2).area_mm2, 2 * math.pi * 9.5**2 / 4)
