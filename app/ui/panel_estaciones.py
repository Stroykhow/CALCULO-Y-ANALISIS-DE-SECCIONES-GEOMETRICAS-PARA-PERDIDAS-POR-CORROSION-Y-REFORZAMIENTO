"""Revisión por estaciones en la vista «Cálculo»: estribos, tabla de estaciones y resultados.

``PanelEstaciones`` maneja los estribos y las estaciones (x, sección dañada,
pérdida de acero y de estribos) y devuelve ``(Estribos, [Estacion])``.
``resultados_estaciones`` arma el aviso, la gráfica y la tabla de resultados.
"""

import flet as ft

from app import estaciones, graficas
from app.ui import estilos as es
from app.ui.compat import AJUSTE_CONTENER, _acepta, avisar, boton, imagen_png
from app.validacion import leer_numero

AYUDA = ("Genere las estaciones con la luz de la viga y luego escriba el daño medido en "
         "cada una. «Dañada» usa las cotas de la sección inspeccionada.")


def _numero(etiqueta, valor="", col=None, expand=None):
    return ft.TextField(label=etiqueta, value=valor, dense=True, border_radius=8, col=col,
                        expand=expand, keyboard_type=ft.KeyboardType.NUMBER,
                        **es.estilo_campo())


def _casilla(valor=False, **kwargs):
    extra = {"fill_color": es.AZUL} if _acepta(ft.Checkbox, "fill_color") else {}
    return ft.Checkbox(value=valor, **extra, **kwargs)


def _encabezado(texto, expand):
    return ft.Text(texto, expand=expand, size=12, color=es.SOBRE_ENTRADA,
                   weight=ft.FontWeight.W_600)


class PanelEstaciones:
    """Formulario de la revisión por estaciones. ``control`` va en la tarjeta de entrada."""

    def __init__(self, page, luz_texto):
        self.page = page
        self.luz_texto = luz_texto            # función que devuelve el texto del campo de luz
        cuarto = {"xs": 6, "sm": 3}
        self.txt_diametro = _numero("Ø estribo (mm)", "9.5", cuarto)
        self.txt_ramas = _numero("Ramas", "2", cuarto)
        self.txt_separacion = _numero("Separación s (m)", "0.20", cuarto)
        self.txt_fyt = _numero("fyt (MPa)", "420", cuarto)
        self.txt_paso = _numero("Paso (m)", "1", expand=1)
        self.filas = []                       # dicts con los controles de cada estación
        self.lista = ft.Column(spacing=6)
        self.chk = _casilla(False, label="Revisar por estaciones (flexión y cortante)",
                            on_change=self._cambiar)
        self.bloque = ft.Column(spacing=10, visible=False, controls=self._contenido())
        self.control = ft.Column(spacing=10, controls=[
            es.etiqueta_seccion("Revisión a lo largo de la viga", es.SUAVE_ENTRADA),
            self.chk, self.bloque])

    def _contenido(self):
        return [
            ft.Text("Estribos (cortante, NSR-10 C.11)", size=12.5, color=es.SOBRE_ENTRADA,
                    weight=ft.FontWeight.W_600),
            ft.ResponsiveRow([self.txt_diametro, self.txt_ramas, self.txt_separacion,
                              self.txt_fyt], spacing=10, run_spacing=10),
            ft.Row([self.txt_paso,
                    boton("Generar estaciones", self._on_generar, ft.Icons.STRAIGHTEN,
                          "outlined", style=es.estilo_boton(None, es.SOBRE_ENTRADA,
                                                            es.SOBRE_ENTRADA))]),
            ft.Text(AYUDA, size=11.5, color=es.SUAVE_ENTRADA),
            ft.Row([_encabezado("x (m)", 2), _encabezado("Dañada", 2),
                    _encabezado("Acero (%)", 2), _encabezado("Estribos (%)", 2),
                    ft.Container(width=40)]),
            self.lista,
        ]

    def _cambiar(self, e):
        self.bloque.visible = bool(self.chk.value)
        self.page.update()

    # ------------------------------------------------------------------ filas
    def _crear_filas(self, lista):
        self.filas = []
        self.lista.controls = []
        for estacion in lista:
            self._agregar_fila(estacion)

    def _agregar_fila(self, e):
        campos = dict(x=_numero(None, f"{e.x:g}", expand=2),
                      danada=_casilla(e.danada),
                      acero=_numero(None, f"{e.perdida_acero:g}", expand=2),
                      estribos=_numero(None, f"{e.perdida_estribos:g}", expand=2))
        fila = ft.Row(vertical_alignment=ft.CrossAxisAlignment.START, spacing=8)
        quitar = ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=es.SUAVE_ENTRADA,
                               tooltip="Quitar estación",
                               on_click=lambda ev, f=fila: self._quitar(f))
        fila.controls = [campos["x"], ft.Container(campos["danada"], expand=2),
                         campos["acero"], campos["estribos"], quitar]
        campos["fila"] = fila
        self.filas.append(campos)
        self.lista.controls.append(fila)

    def _quitar(self, fila):
        self.filas = [f for f in self.filas if f["fila"] is not fila]
        self.lista.controls = [f["fila"] for f in self.filas]
        self.page.update()

    def _on_generar(self, e):
        luz, e_luz = leer_numero(self.luz_texto())
        paso, e_paso = leer_numero(self.txt_paso.value)
        if e_luz or e_paso:
            avisar(self.page, "Escriba primero la luz de la viga y un paso mayor que 0.",
                   error=True)
            return
        if luz / paso > 200:
            avisar(self.page, "Son demasiadas estaciones: use un paso más grande.", error=True)
            return
        self._crear_filas(estaciones.generar_estaciones(luz, paso))
        avisar(self.page, f"Se generaron {len(self.filas)} estaciones. Escriba el daño de cada una.")

    # ------------------------------------------------------------------ datos
    def llenar(self, estribos, lista):
        """Pone en el formulario unos estribos y estaciones; con None desactiva la revisión."""
        self.chk.value = self.bloque.visible = estribos is not None
        if estribos is None:
            self._crear_filas([])
            return
        for campo, valor in ((self.txt_diametro, estribos.diametro_mm),
                             (self.txt_ramas, estribos.ramas),
                             (self.txt_separacion, estribos.separacion),
                             (self.txt_fyt, estribos.fyt)):
            campo.value, campo.error_text = f"{valor:g}", None
        self._crear_filas(lista)

    def limpiar(self):
        self._crear_filas([])

    def leer(self, errores):
        """Devuelve (Estribos, [Estacion]) o None si la revisión está desactivada."""
        if not self.chk.value:
            return None
        estribos = self._leer_estribos(errores)
        lista = self._leer_filas(errores)
        if not lista and not any("Estación" in m for m in errores):
            errores.append("Estaciones: pulse «Generar estaciones» o desactive la revisión")
        return (estribos, lista) if estribos else None

    def _leer_estribos(self, errores):
        valores = {}
        for clave, campo, etiqueta in (("diametro_mm", self.txt_diametro, "Ø estribo"),
                                       ("ramas", self.txt_ramas, "Ramas"),
                                       ("separacion", self.txt_separacion, "Separación s"),
                                       ("fyt", self.txt_fyt, "fyt")):
            valor, error = leer_numero(campo.value)
            if error is None and clave == "ramas" and valor != int(valor):
                error = "Debe ser un número entero"
            es.marcar_campo(campo, error, etiqueta, errores)
            valores[clave] = valor
        if None in valores.values():
            return None
        return estaciones.Estribos(valores["diametro_mm"], int(valores["ramas"]),
                                   valores["separacion"], valores["fyt"])

    def _leer_filas(self, errores):
        lista = []
        for i, f in enumerate(self.filas, start=1):
            x, e_x = leer_numero(f["x"].value, positivo=False)
            acero, e_a = leer_numero(f["acero"].value, positivo=False, obligatorio=False)
            estribos, e_e = leer_numero(f["estribos"].value, positivo=False, obligatorio=False)
            for campo, error, nombre in ((f["x"], e_x, "x"), (f["acero"], e_a, "acero"),
                                         (f["estribos"], e_e, "estribos")):
                es.marcar_campo(campo, error, f"Estación {i}, {nombre}", errores)
            if not (e_x or e_a or e_e):
                lista.append(estaciones.Estacion(x, bool(f["danada"].value), acero or 0.0,
                                                 estribos or 0.0))
        return lista


# ---------------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------------
def resultados_estaciones(rev):
    """Aviso, gráfica y tabla de la revisión por estaciones."""
    return [_aviso(rev), _figura(rev), _tabla(rev)]


def _aviso(rev):
    color, fondo, _ = es.SEVERIDAD["VERDE" if rev.cumple_todo else "ROJO"]
    return ft.Container(
        padding=18, border_radius=14, bgcolor=fondo, border=es.borde(1, color),
        content=ft.Row(spacing=16, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
            ft.Icon(ft.Icons.LINEAR_SCALE, color=color, size=44),
            ft.Column(spacing=2, expand=True, controls=[
                ft.Text("Revisión por estaciones · flexión y cortante", size=13, color=color,
                        weight=ft.FontWeight.W_600),
                ft.Text(rev.resumen(), size=16, weight=ft.FontWeight.BOLD, color=es.TEXTO),
                ft.Text(f"wu = {rev.wu:.1f} kN/m · estribos Ø{rev.estribos.diametro_mm:g} mm de "
                        f"{rev.estribos.ramas} ramas cada {rev.estribos.separacion:g} m",
                        size=13, color=es.TEXTO_SUAVE),
            ]),
            es.chip("CUMPLE" if rev.cumple_todo else "NO CUMPLE", es.TARJETA, color),
        ]),
    )


def _figura(rev):
    png = graficas.figura_a_png(graficas.figura_estaciones(rev, oscuro=True))
    return es.tarjeta(es.titulo("Resistencia frente a demanda a lo largo de la viga",
                                ft.Icons.SHOW_CHART),
                      imagen_png(png, fit=AJUSTE_CONTENER), padding=14)


def _tabla(rev):
    def fila(f):
        color, fondo, _ = es.SEVERIDAD["VERDE" if f["cumple"] else "ROJO"]
        textos = [f"{f['x']:g}", "Dañada" if f["danada"] else "Sana", f"{f['perdida_acero']:g}",
                  f"{f['perdida_estribos']:g}", f"{f['mu']:,.0f}", f"{f['phi_mn']:,.0f}",
                  f"{f['vu']:,.0f}", f"{f['phi_vn']:,.0f}", f"{f['relacion']:.2f}"]
        return ft.DataRow(cells=[ft.DataCell(ft.Text(t)) for t in textos] +
                          [ft.DataCell(es.chip("CUMPLE" if f["cumple"] else "NO CUMPLE",
                                               color, fondo))])

    tabla = ft.DataTable(
        heading_row_color=es.PRIMARIO_CLARO, column_spacing=18,
        columns=es.encabezado_tabla("x (m)", "Sección", "Acero (%)", "Estribos (%)",
                                    "Mu (kN·m)", "φMn (kN·m)", "Vu (kN)", "φVn (kN)",
                                    "D/R", "Chequeo"),
        rows=[fila(f) for f in rev.filas()])
    return es.tarjeta(es.titulo("Resultados por estación", ft.Icons.TABLE_CHART,
                                "D/R = demanda / resistencia (la peor entre flexión y cortante)"),
                      ft.Row([tabla], scroll=ft.ScrollMode.AUTO))
