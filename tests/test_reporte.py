"""Pruebas de la memoria de cálculo."""

import pytest

from app import modelo, reporte


def _calculo(con_flexion=True):
    from app import flexion
    calculo = dict(id=1, proyecto="Puente ejemplo", nombre="Viga 1",
                   tipo_seccion=modelo.EJEMPLO["tipo"], param_ideal=modelo.EJEMPLO["ideal"],
                   param_mod=modelo.EJEMPLO["modificada"], edad_anios=modelo.EJEMPLO["edad_anios"])
    if con_flexion:
        calculo["datos_flexion"] = flexion.EJEMPLO.a_diccionario()
        calculo["capas"] = [dict(n_barras=c.n_barras, diametro_mm=c.diametro_mm, y=c.y)
                            for c in flexion.EJEMPLO.capas]
    return calculo


def test_contexto_tiene_tablas_y_chequeo():
    calculo = _calculo()
    contexto = reporte.contexto_memoria(calculo, reporte.recalcular(calculo), "Autores")
    assert len(contexto["parametros"]) == len(modelo.PARAMETROS["bulb_tee"])
    assert len(contexto["propiedades"]) == len(modelo.PROPIEDADES)
    assert contexto["chequeo"].startswith("No, supera el 10 %")     # 12.91 % de pérdida
    assert contexto["severidad"] == "NARANJA"


def test_contexto_de_flexion():
    calculo = _calculo()
    contexto = reporte.contexto_memoria(calculo, reporte.recalcular(calculo))
    assert len(contexto["flex_capas"]) == 2
    assert contexto["flex_chequeo"] == "CUMPLE"
    assert "33.9 años" in contexto["flex_vida"]


def test_contexto_sin_flexion():
    calculo = _calculo(con_flexion=False)
    contexto = reporte.contexto_memoria(calculo, reporte.recalcular(calculo))
    assert contexto["flex_capas"] == [] and contexto["flex_chequeo"] == "No evaluado"


def test_genera_docx(tmp_path):
    pytest.importorskip("docxtpl")
    from docx import Document
    ruta = reporte.generar_memoria(_calculo(), tmp_path / "memoria.docx", "Autores")
    texto = "\n".join(p.text for p in Document(ruta).paragraphs)
    assert "{{" not in texto and "NARANJA" in texto
    assert len(Document(ruta).inline_shapes) == 3
