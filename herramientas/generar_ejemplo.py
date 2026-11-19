"""Genera ejemplos/memoria_ejemplo.docx con el caso de ejemplo del modelo.

Uso (con el entorno virtual activado):  python herramientas/generar_ejemplo.py
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app import flexion, modelo, reporte  # noqa: E402

calculo = dict(
    id=1, proyecto="Puente ejemplo", nombre="Viga exterior - inspección",
    tipo_seccion=modelo.EJEMPLO["tipo"], param_ideal=modelo.EJEMPLO["ideal"],
    param_mod=modelo.EJEMPLO["modificada"], edad_anios=modelo.EJEMPLO["edad_anios"],
    datos_flexion=flexion.EJEMPLO.a_diccionario(),
    capas=[dict(n_barras=c.n_barras, diametro_mm=c.diametro_mm, y=c.y)
           for c in flexion.EJEMPLO.capas],
)
autores = sys.argv[1] if len(sys.argv) > 1 else ""
ruta = reporte.generar_memoria(calculo, RAIZ / "ejemplos" / "memoria_ejemplo.docx", autores)
print("Memoria de ejemplo generada en", ruta)
