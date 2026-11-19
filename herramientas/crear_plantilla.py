"""Crea la plantilla Jinja ``plantillas/memoria.docx`` usada por docxtpl.

La plantilla ya está en el repositorio; este script solo se usa si se quiere
regenerarla desde cero:  python herramientas/crear_plantilla.py
También se puede abrir y editar directamente en Word, respetando las etiquetas.
"""

import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

RAIZ = Path(__file__).resolve().parent.parent
AZUL = RGBColor(0x0D, 0x3B, 0x66)


def sombrear(celda, color="0D3B66"):
    tc_pr = celda._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    tc_pr.append(shd)


def tabla_con_bucle(doc, encabezados, variable, item, campos, anchos=None):
    """Tabla con encabezado + filas repetidas con {%tr for %} ... {%tr endfor %}."""
    tabla = doc.add_table(rows=4, cols=len(encabezados))
    tabla.style = "Table Grid"
    tabla.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, texto in enumerate(encabezados):
        celda = tabla.rows[0].cells[i]
        celda.text = ""
        run = celda.paragraphs[0].add_run(texto)
        run.bold = True
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        run.font.size = Pt(9)
        sombrear(celda)
    tabla.rows[1].cells[0].text = f"{{%tr for {item} in {variable} %}}"
    for i, campo in enumerate(campos):
        celda = tabla.rows[2].cells[i]
        celda.text = ""
        run = celda.paragraphs[0].add_run(f"{{{{ {item}.{campo} }}}}")
        run.font.size = Pt(9)
    tabla.rows[3].cells[0].text = "{%tr endfor %}"
    if anchos:
        for fila in tabla.rows:
            for celda, ancho in zip(fila.cells, anchos):
                celda.width = Cm(ancho)
    doc.add_paragraph()
    return tabla


def ecuacion(doc, texto):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(texto)
    run.italic = True
    run.font.name = "Cambria Math"
    return p


def crear(ruta):
    doc = Document()
    estilo = doc.styles["Normal"]
    estilo.font.name = "Calibri"
    estilo.font.size = Pt(10.5)
    for seccion in doc.sections:
        seccion.left_margin = seccion.right_margin = Cm(2.2)
        seccion.top_margin = seccion.bottom_margin = Cm(2.0)
        cab = seccion.header.paragraphs[0]
        cab.text = ("Universidad Distrital Francisco José de Caldas · Facultad Tecnológica · "
                    "Ingeniería Civil\tMemoria de cálculo")
        cab.runs[0].font.size = Pt(8)
        pie = seccion.footer.paragraphs[0]
        pie.text = "Proyecto: {{ proyecto }} · Cálculo: {{ calculo }} · {{ fecha }}"
        pie.runs[0].font.size = Pt(8)

    titulo = doc.add_paragraph()
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = titulo.add_run("MEMORIA DE CÁLCULO")
    run.bold = True
    run.font.size = Pt(18)
    run.font.color.rgb = AZUL
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.add_run("Análisis de secciones geométricas por pérdida de sección (corrosión) "
                "y reforzamiento").italic = True

    datos = doc.add_table(rows=6, cols=2)
    datos.style = "Table Grid"
    for fila, (etiqueta, valor) in zip(datos.rows, [
        ("Proyecto", "{{ proyecto }}"), ("Cálculo", "{{ calculo }}"),
        ("Fecha", "{{ fecha }}"), ("Elaboró", "{{ autores }}"),
        ("Tipo de sección", "{{ tipo_seccion }}"),
        ("Edad de la estructura en la inspección", "{{ edad }}"),
    ]):
        fila.cells[0].text = ""
        fila.cells[0].paragraphs[0].add_run(etiqueta).bold = True
        fila.cells[1].text = valor
        fila.cells[0].width, fila.cells[1].width = Cm(6), Cm(10.5)
    doc.add_paragraph()

    doc.add_heading("1. Objeto", level=1)
    doc.add_paragraph(
        "Cuantificar la variación de las propiedades geométricas y del módulo resistente de "
        "una sección transversal modificada (pérdida de sección por corrosión, desgaste o "
        "daño, o aumento por reforzamiento) respecto a la sección ideal de diseño, clasificar "
        "la severidad del daño y estimar cuándo se alcanzarían los umbrales de intervención "
        "si el daño continúa avanzando.")

    doc.add_heading("2. Datos de entrada", level=1)
    doc.add_paragraph("Cotas de la sección ideal (diseño) y de la sección modificada "
                      "(estado inspeccionado o reforzado):")
    tabla_con_bucle(doc, ["Cota", "Descripción", "Unidad", "Ideal", "Modificada", "Var. (%)"],
                    "parametros", "p",
                    ["clave", "descripcion", "unidad", "ideal", "modificada", "variacion"],
                    anchos=[1.5, 5.5, 1.5, 2.5, 2.5, 2.0])

    doc.add_heading("3. Procedimiento y ecuaciones", level=1)
    doc.add_paragraph(
        "La sección se describe como un polígono de vértices (xᵢ, yᵢ), i = 1…n, recorrido "
        "en orden (geometría generada con la librería pysections). Las propiedades se "
        "obtienen con el teorema de Green (fórmulas del polígono), con cᵢ = xᵢ·yᵢ₊₁ − xᵢ₊₁·yᵢ:")
    ecuacion(doc, "A = ½ Σ cᵢ          Qx = ⅙ Σ cᵢ (yᵢ + yᵢ₊₁)          Qy = ⅙ Σ cᵢ (xᵢ + xᵢ₊₁)")
    ecuacion(doc, "xc = Qy / A          yc = Qx / A")
    ecuacion(doc, "Ixx = (1/12) Σ cᵢ (yᵢ² + yᵢ·yᵢ₊₁ + yᵢ₊₁²) − A·yc²")
    ecuacion(doc, "Iyy = (1/12) Σ cᵢ (xᵢ² + xᵢ·xᵢ₊₁ + xᵢ₊₁²) − A·xc²")
    ecuacion(doc, "Zx,inf = Ixx / yc          Zx,sup = Ixx / (h − yc)          "
                  "Zx = mín(Zx,inf ; Zx,sup)")
    doc.add_paragraph("La variación de cada propiedad usa la sección ideal como referencia:")
    ecuacion(doc, "Variación (%) = (Modificada − Ideal) / Ideal × 100          "
                  "Pérdida (%) = −Variación")
    doc.add_paragraph(
        "La severidad se clasifica según la pérdida del módulo resistente crítico Zx: "
        "VERDE (< 10 %) mantenimiento preventivo; NARANJA (10 % a 25 %) rediseño de la "
        "capacidad nominal; ROJO (> 25 %) intervención inminente.")

    doc.add_heading("4. Resultados", level=1)
    tabla_con_bucle(doc, ["Propiedad", "Unidad", "Ideal", "Modificada", "Diferencia", "Var. (%)"],
                    "propiedades", "r",
                    ["propiedad", "unidad", "ideal", "modificada", "diferencia", "variacion"],
                    anchos=[5.0, 1.5, 2.5, 2.5, 2.5, 1.8])
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("{{ grafica_geometria }}")
    leyenda = doc.add_paragraph("Figura 1. Sección ideal y sección modificada con sus ejes neutros.")
    leyenda.alignment = WD_ALIGN_PARAGRAPH.CENTER
    leyenda.runs[0].italic = True

    doc.add_heading("5. Proyección de la degradación", level=1)
    doc.add_paragraph(
        "Se supone que el daño avanza de forma lineal desde la sección ideal (α = 0) hasta la "
        "sección inspeccionada (α = 1) y continúa al mismo ritmo. Como los vértices son "
        "funciones lineales de las cotas, la sección con nivel de daño α es:")
    ecuacion(doc, "P(α) = P_ideal + α · (P_modificada − P_ideal)          t(α) = α · t_inspección")
    doc.add_paragraph(
        "Las propiedades se evalúan de forma vectorizada (NumPy) sobre una malla de α, y el "
        "nivel de daño en que Zx cruza cada umbral se obtiene como la raíz de la ecuación "
        "siguiente con el método de Brent (scipy.optimize.brentq):")
    ecuacion(doc, "f(α) = 100 · Zx(α) / Zx,ideal − (100 − umbral) = 0")
    tabla_con_bucle(doc, ["Umbral de pérdida de Zx", "Nivel de daño α*", "Edad (años)",
                          "Vida remanente (años)"],
                    "umbrales", "u", ["umbral", "alfa", "tiempo", "remanente"],
                    anchos=[4.5, 3.5, 3.5, 4.0])
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("{{ grafica_capacidad }}")
    leyenda = doc.add_paragraph("Figura 2. Capacidad relativa de A, Ixx y Zx con el avance del daño.")
    leyenda.alignment = WD_ALIGN_PARAGRAPH.CENTER
    leyenda.runs[0].italic = True

    doc.add_heading("6. Análisis a flexión (NSR-10)", level=1)
    doc.add_paragraph("{{ flex_estado }}")
    doc.add_paragraph(
        "Demanda: viga simplemente apoyada con carga distribuida. El peso propio es el área "
        "de la sección por 24 kN/m³ y se suma a la carga muerta adicional (NSR-10 B.2.4):")
    ecuacion(doc, "wu = máx(1.2·D + 1.6·L ; 1.4·D)          Mu = wu · L² / 8")
    doc.add_paragraph(
        "Resistencia: bloque rectangular equivalente de Whitney sobre la forma real de la "
        "sección y compatibilidad de deformaciones en cada capa de barras (εcu = 0.003, "
        "Es = 200 000 MPa). La profundidad del eje neutro c se obtiene de la condición de "
        "equilibrio, resuelta con el método de Brent (scipy.optimize.brentq):")
    ecuacion(doc, "a = β1·c          C = 0.85·f'c·A_comprimida(a)          "
                  "εs = 0.003·(d − c)/c          fs = Es·εs ≤ fy")
    ecuacion(doc, "C − Σ As·fs = 0          Mn = C·yC − Σ As·fs·ys          "
                  "φ = 0.90 si εt ≥ 0.005 (NSR-10 C.9.3.2)")
    ecuacion(doc, "Mcr = fr·Ig / yb,  fr = 0.62·√f'c          Chequeo: φMn ≥ Mu")
    tabla_con_bucle(doc, ["Dato", "Unidad", "Valor"], "flex_datos", "x",
                    ["dato", "unidad", "valor"], anchos=[9.0, 2.5, 4.0])
    tabla_con_bucle(doc, ["Capa", "Barras", "Ø (mm)", "y (m)", "d (m)", "As sana (mm²)",
                          "As corroída (mm²)", "fs (MPa)"],
                    "flex_capas", "k",
                    ["capa", "n", "diametro", "y", "d", "as_ideal", "as_mod", "fs"],
                    anchos=[1.3, 1.5, 1.6, 1.6, 1.6, 2.6, 2.8, 2.0])
    tabla_con_bucle(doc, ["Resultado", "Unidad", "Sección ideal", "Sección inspeccionada"],
                    "flex_resultados", "f", ["resultado", "unidad", "ideal", "modificada"],
                    anchos=[6.5, 2.0, 3.5, 4.0])
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("{{ grafica_flexion }}")
    leyenda = doc.add_paragraph("Figura 3. Sección inspeccionada: bloque de compresión, barras "
                                "y diagrama de deformaciones.")
    leyenda.alignment = WD_ALIGN_PARAGRAPH.CENTER
    leyenda.runs[0].italic = True
    doc.add_paragraph("{{ flex_vida }}")

    doc.add_heading("7. Chequeo y conclusión", level=1)
    resumen = doc.add_table(rows=7, cols=2)
    resumen.style = "Table Grid"
    for fila, (etiqueta, valor) in zip(resumen.rows, [
        ("Pérdida de área", "{{ perdida_area }} %"),
        ("Pérdida de inercia Ixx", "{{ perdida_ixx }} %"),
        ("Pérdida de módulo resistente Zx", "{{ perdida_zx }} %"),
        ("Clasificación", "{{ severidad }}"),
        ("Dictamen", "{{ dictamen }}"),
        ("Chequeo Zx,mod ≥ 0.90 · Zx,ideal", "{{ chequeo }}"),
        ("Chequeo a flexión φMn ≥ Mu (sección inspeccionada)", "{{ flex_chequeo }}"),
    ]):
        fila.cells[0].text = ""
        fila.cells[0].paragraphs[0].add_run(etiqueta).bold = True
        fila.cells[1].text = valor
    doc.add_paragraph()
    doc.add_paragraph("{{ conclusion }}")
    doc.add_paragraph("{{ flex_conclusion }}")

    doc.add_heading("8. Referencias", level=1)
    for ref in [
        "Gere, J. M., & Goodno, B. J. (2013). Mecánica de materiales (8.ª ed.). Cengage Learning.",
        "Steger, C. (1996). On the calculation of arbitrary moments of polygons. "
        "Technical Report FGBV-96-05, Technische Universität München.",
        "AASHTO (2020). LRFD Bridge Design Specifications (9.ª ed.).",
        "Asociación Colombiana de Ingeniería Sísmica (2010). Reglamento NSR-10, Títulos B y C.",
        "McCormac, J. C., & Brown, R. H. (2017). Diseño de concreto reforzado (10.ª ed.). "
        "Alfaomega.",
        "Ramírez Vargas, C. D. (2025). sections.py — librería de propiedades de secciones "
        "(GPL-3.0).",
    ]:
        doc.add_paragraph(ref, style="List Bullet")

    ruta.parent.mkdir(parents=True, exist_ok=True)
    doc.save(ruta)
    return ruta


if __name__ == "__main__":
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "plantillas" / "memoria.docx"
    print("Plantilla creada en", crear(destino))
