"""Generación de la memoria de cálculo en Word con docxtpl.

La plantilla ``plantillas/memoria.docx`` es un documento de Word con etiquetas
Jinja ({{ variable }}, {%tr for %} para filas de tabla). Se rellena con los
datos de un cálculo guardado en la base de datos.
"""

import tempfile
from datetime import date
from pathlib import Path

from app import flexion, graficas, modelo

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLA = RAIZ / "plantillas" / "memoria.docx"
CARPETA_REPORTES = RAIZ / "reportes"


def _fmt(valor, decimales=6):
    return f"{valor:.{decimales}g}" if abs(valor) >= 1e-12 else "0"


def datos_flexion_de(calculo):
    """``DatosFlexion`` de un cálculo guardado, o None si no se evaluó a flexión."""
    if calculo.get("datos_flexion") and calculo.get("capas"):
        return flexion.DatosFlexion.desde_diccionario(calculo["datos_flexion"], calculo["capas"])
    return None


def recalcular(calculo):
    """Reconstruye el ``Resultado`` a partir de un cálculo guardado en SQLite."""
    return modelo.comparar(calculo["tipo_seccion"], calculo["param_ideal"],
                           calculo["param_mod"], calculo.get("edad_anios"),
                           datos_flexion_de(calculo))


def _contexto_flexion(resultado):
    """Variables de la sección de flexión de la plantilla."""
    f = resultado.flexion
    if f is None:
        return dict(flex_estado="No se evaluó la flexión en este cálculo.", flex_datos=[],
                    flex_capas=[], flex_resultados=[], flex_chequeo="No evaluado",
                    flex_vida="—", flex_conclusion="")
    i, m, d = f.ideal, f.modificada, f.datos
    num = lambda v, fmt="{:,.2f}": fmt.format(v)          # noqa: E731
    datos = [
        ("Resistencia del concreto f'c", "MPa", num(d.fc, "{:g}")),
        ("Fluencia del acero fy", "MPa", num(d.fy, "{:g}")),
        ("Factor del bloque β1", "-", num(i.beta1, "{:.3f}")),
        ("Pérdida de área del acero por corrosión", "%", num(d.perdida_acero, "{:g}")),
        ("Luz de la viga (simplemente apoyada) L", "m", num(d.luz, "{:g}")),
        ("Carga muerta adicional", "kN/m", num(d.carga_muerta, "{:g}")),
        ("Carga viva", "kN/m", num(d.carga_viva, "{:g}")),
    ]
    capas = [dict(capa=str(k), n=str(c["n_barras"]), diametro=f"{c['diametro_mm']:g}",
                  y=f"{c['y']:.3f}", d=f"{c['d']:.3f}", as_ideal=f"{c['as_mm2']:,.0f}",
                  as_mod=f"{cm['as_mm2']:,.0f}", fs=f"{cm['fs']:,.0f}")
             for k, (c, cm) in enumerate(zip(i.capas, m.capas), start=1)]
    filas = [
        ("Área total de acero As", "mm²", i.as_total_mm2, m.as_total_mm2, "{:,.0f}"),
        ("Peso propio (24 kN/m³ × A)", "kN/m", i.peso_propio, m.peso_propio, "{:,.2f}"),
        ("Carga última wu", "kN/m", i.wu, m.wu, "{:,.2f}"),
        ("Momento último Mu", "kN·m", i.mu, m.mu, "{:,.1f}"),
        ("Profundidad del eje neutro c", "cm", i.c * 100, m.c * 100, "{:,.2f}"),
        ("Altura del bloque a = β1·c", "cm", i.a * 100, m.a * 100, "{:,.2f}"),
        ("Deformación del acero extremo εt", "‰", i.eps_t * 1000, m.eps_t * 1000, "{:,.2f}"),
        ("Factor de reducción φ", "-", i.phi, m.phi, "{:.3f}"),
        ("Resistencia nominal Mn", "kN·m", i.mn, m.mn, "{:,.1f}"),
        ("Resistencia de diseño φMn", "kN·m", i.phi_mn, m.phi_mn, "{:,.1f}"),
        ("Momento de agrietamiento Mcr", "kN·m", i.mcr, m.mcr, "{:,.1f}"),
        ("Relación Mu / φMn", "-", i.relacion, m.relacion, "{:.3f}"),
    ]
    resultados = [dict(resultado=n, unidad=u, ideal=fmt.format(a), modificada=fmt.format(b))
                  for n, u, a, b, fmt in filas]
    resultados.append(dict(resultado="Chequeo φMn ≥ Mu", unidad="-",
                           ideal="CUMPLE" if i.cumple else "NO CUMPLE",
                           modificada="CUMPLE" if m.cumple else "NO CUMPLE"))

    if f.alfa_falla == 0.0:
        vida = "La viga no cumple a flexión ni con la sección de diseño."
    elif f.tiempo_falla is not None:
        restante = f.tiempo_falla - f.edad_anios
        vida = (f"Si el daño avanza al mismo ritmo, φMn deja de cubrir Mu a los "
                f"{f.tiempo_falla:.1f} años ({'hace' if restante < 0 else 'dentro de'} "
                f"{abs(restante):.1f} años).")
    elif f.alfa_falla is not None:
        vida = f"φMn deja de cubrir Mu con un nivel de daño α = {f.alfa_falla:.2f}."
    else:
        vida = "φMn sigue cubriendo Mu en todo el rango de daño proyectado."

    avisos = []
    if not m.ductil:
        avisos.append("εt < 0.004: la sección no cumple la deformación mínima de NSR-10 C.10.3.5.")
    if not m.cumple_as_min:
        avisos.append(f"El acero es menor que As,mín = {m.as_min_mm2:,.0f} mm² (NSR-10 C.10.5.1).")
    conclusion = (f"A flexión, la sección inspeccionada tiene φMn = {m.phi_mn:,.1f} kN·m frente a "
                  f"Mu = {m.mu:,.1f} kN·m (Mu/φMn = {m.relacion:.2f}): "
                  f"{'CUMPLE' if m.cumple else 'NO CUMPLE'}. La resistencia de diseño bajó "
                  f"{f.perdida_phi_mn:.1f} % respecto a la viga sana. {vida} " + " ".join(avisos))
    return dict(
        flex_estado="Se evaluó la viga simplemente apoyada con las cargas y el refuerzo indicados.",
        flex_datos=[dict(dato=a, unidad=b, valor=c) for a, b, c in datos],
        flex_capas=capas, flex_resultados=resultados,
        flex_chequeo="CUMPLE" if m.cumple else "NO CUMPLE",
        flex_vida=vida, flex_conclusion=conclusion.strip(),
    )


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
        **_contexto_flexion(resultado),
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
        contexto["grafica_flexion"] = ""
        if resultado.flexion is not None:
            img_flex = graficas.guardar_figura(
                graficas.figura_flexion(resultado.flexion.modificada), Path(tmp) / "flexion.png")
            contexto["grafica_flexion"] = InlineImage(plantilla, str(img_flex), width=Mm(160))
        plantilla.render(contexto)
        plantilla.save(ruta_salida)
    return Path(ruta_salida)
