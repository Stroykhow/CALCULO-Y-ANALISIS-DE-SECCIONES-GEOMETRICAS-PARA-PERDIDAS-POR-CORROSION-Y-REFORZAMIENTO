"""Generación de la memoria de cálculo en Word con docxtpl.

La plantilla ``plantillas/memoria.docx`` es un documento de Word con etiquetas
Jinja ({{ variable }}, {%tr for %} para filas de tabla). Se rellena con los
datos de un cálculo guardado en la base de datos.
"""

import tempfile
from datetime import date
from pathlib import Path

from app import graficas, modelo

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLA = RAIZ / "plantillas" / "memoria.docx"
CARPETA_REPORTES = RAIZ / "reportes"


def _fmt(valor, decimales=6):
    return f"{valor:.{decimales}g}" if abs(valor) >= 1e-12 else "0"


def recalcular(calculo):
    """Reconstruye el ``Resultado`` a partir de un cálculo guardado en SQLite."""
    return modelo.comparar(calculo["tipo_seccion"], calculo["param_ideal"],
                           calculo["param_mod"], calculo.get("edad_anios"))


def contexto_memoria(calculo, resultado, autores=""):
    """Diccionario con todas las variables de la plantilla (sin imágenes)."""
    proy = resultado.proyeccion
    unidades = {c: u for c, _, u in modelo.PARAMETROS[resultado.tipo]}
    descripciones = {c: d for c, d, _ in modelo.PARAMETROS[resultado.tipo]}

    parametros = [
        dict(clave=c, descripcion=descripciones[c], unidad=unidades[c],
             ideal=f"{resultado.ideal_param[c]:.4f}", modificada=f"{resultado.mod_param[c]:.4f}",
             variacion=f"{modelo.variacion_porcentual(resultado.ideal_param[c], resultado.mod_param[c]):+.2f}")
        for c in resultado.ideal_param
    ]
    propiedades = [
        dict(propiedad=f["propiedad"], unidad=f["unidad"], ideal=_fmt(f["ideal"]),
             modificada=_fmt(f["modificada"]), diferencia=_fmt(f["diferencia"]),
             variacion=f"{f['variacion']:+.2f}" if f["clave"] not in ("xc", "ixy") else "—")
        for f in resultado.filas_tabla()
    ]

    umbrales = []
    for umbral in (modelo.UMBRAL_PREVENTIVO, modelo.UMBRAL_INTERVENCION):
        a = proy.alfa_umbral.get(umbral)
        t = proy.tiempo_umbral(umbral)
        umbrales.append(dict(
            umbral=f"{umbral:.0f} %",
            alfa=f"{a:.3f}" if a is not None else "No se alcanza",
            tiempo=f"{t:.1f}" if t is not None else "—",
            remanente=(f"{t - proy.edad_anios:.1f}" if t is not None else "—"),
        ))

    if resultado.perdida_zx < 0:
        conclusion = (f"La sección modificada aumenta el módulo resistente crítico en "
                      f"{-resultado.perdida_zx:.2f} %: el reforzamiento recupera o supera la "
                      f"capacidad de la sección ideal.")
    else:
        conclusion = (f"La sección modificada pierde {resultado.perdida_zx:.2f} % del módulo "
                      f"resistente crítico Zx respecto a la sección ideal.")

    return dict(
        proyecto=calculo.get("proyecto", ""),
        calculo=calculo.get("nombre", ""),
        fecha=date.today().strftime("%d/%m/%Y"),
        autores=autores,
        tipo_seccion=modelo.NOMBRES_TIPO[resultado.tipo],
        edad=f"{proy.edad_anios:.1f} años" if proy.edad_anios else "No indicada",
        parametros=parametros,
        propiedades=propiedades,
        umbrales=umbrales,
        perdida_area=f"{resultado.perdida_area:.2f}",
        perdida_ixx=f"{resultado.perdida_ixx:.2f}",
        perdida_zx=f"{resultado.perdida_zx:.2f}",
        severidad=resultado.severidad,
        dictamen=resultado.dictamen,
        chequeo="CUMPLE" if resultado.cumple else "NO CUMPLE",
        conclusion=conclusion,
    )


def generar_memoria(calculo, ruta_salida=None, autores=""):
    """Genera el .docx de un cálculo guardado y devuelve la ruta del archivo."""
    from docxtpl import DocxTemplate, InlineImage
    from docx.shared import Mm

    resultado = recalcular(calculo)
    if ruta_salida is None:
        CARPETA_REPORTES.mkdir(exist_ok=True)
        nombre = f"memoria_{calculo.get('id', 'nuevo')}_{calculo.get('nombre', '')}"
        nombre = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in nombre)
        ruta_salida = CARPETA_REPORTES / f"{nombre}.docx"

    plantilla = DocxTemplate(PLANTILLA)
    contexto = contexto_memoria(calculo, resultado, autores)
    with tempfile.TemporaryDirectory() as tmp:
        img_geo = graficas.guardar_figura(graficas.figura_geometria(resultado),
                                          Path(tmp) / "geometria.png")
        img_cap = graficas.guardar_figura(graficas.figura_capacidad(resultado),
                                          Path(tmp) / "capacidad.png")
        contexto["grafica_geometria"] = InlineImage(plantilla, str(img_geo), width=Mm(140))
        contexto["grafica_capacidad"] = InlineImage(plantilla, str(img_cap), width=Mm(160))
        plantilla.render(contexto)
        plantilla.save(ruta_salida)
    return Path(ruta_salida)
