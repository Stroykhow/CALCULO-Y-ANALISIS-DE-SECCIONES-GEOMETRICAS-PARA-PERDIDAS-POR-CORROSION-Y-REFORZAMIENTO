"""Pruebas de la memoria de cálculo."""

import pytest

from app import modelo, reporte


def _calculo():
    return dict(id=1, proyecto="Puente ejemplo", nombre="Viga 1",
                tipo_seccion=modelo.EJEMPLO["tipo"], param_ideal=modelo.EJEMPLO["ideal"],
                param_mod=modelo.EJEMPLO["modificada"], edad_anios=modelo.EJEMPLO["edad_anios"])


def test_contexto_tiene_tablas_y_chequeo():
    calculo = _calculo()
    contexto = reporte.contexto_memoria(calculo, reporte.recalcular(calculo), "Autores")
    assert len(contexto["parametros"]) == len(modelo.PARAMETROS["bulb_tee"])
    assert len(contexto["propiedades"]) == len(modelo.PROPIEDADES)
    assert contexto["chequeo"] in ("CUMPLE", "NO CUMPLE")
    assert contexto["severidad"] == "NARANJA"


def test_genera_docx(tmp_path):
    pytest.importorskip("docxtpl")
    from docx import Document
    ruta = reporte.generar_memoria(_calculo(), tmp_path / "memoria.docx", "Autores")
    texto = "\n".join(p.text for p in Document(ruta).paragraphs)
    assert "{{" not in texto and "NARANJA" in texto
    assert len(Document(ruta).inline_shapes) == 2
