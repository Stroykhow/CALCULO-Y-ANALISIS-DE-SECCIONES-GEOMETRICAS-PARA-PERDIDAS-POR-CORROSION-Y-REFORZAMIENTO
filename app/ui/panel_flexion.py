"""Parte de flexión de la vista «Cálculo»: formulario de acero y cargas, y resultados.

``PanelFlexion`` maneja los campos (f'c, fy, pérdida de acero, capas de barras,
luz y cargas) y devuelve un ``flexion.DatosFlexion``. ``resultados_flexion``
arma los controles que muestran el chequeo φMn ≥ Mu.
"""

import flet as ft

from app import flexion, graficas
from app.ui import estilos as es
from app.ui.compat import AJUSTE_CONTENER, _acepta, boton, imagen_png
from app.validacion import leer_numero

AYUDA_DIAMETROS = "Ø: No.4 = 12.7 · No.5 = 15.9 · No.6 = 19.1 · No.8 = 25.4 mm"
AYUDA_CARGAS = ("Viga simplemente apoyada. El peso propio se suma solo (área × 24 kN/m³). "
                "Mu = (1.2D + 1.6L)·L²/8.")


def _numero(etiqueta, valor="", col=None, expand=None):
    """Campo numérico con el estilo de la tarjeta de entrada."""
    return ft.TextField(label=etiqueta, value=valor, dense=True, border_radius=8, col=col,
                        expand=expand, keyboard_type=ft.KeyboardType.NUMBER,
                        **es.estilo_campo())


def _encabezado(texto, expand):
    return ft.Text(texto, expand=expand, size=12.5, color=es.SOBRE_ENTRADA,
                   weight=ft.FontWeight.W_600)


class PanelFlexion:
    """Formulario de flexión. ``control`` es lo que se pone en la tarjeta de entrada."""

    def __init__(self, page):
        self.page = page
        tercio = {"xs": 12, "sm": 4}
        self.txt_fc = _numero("f'c concreto (MPa)", "28", tercio)
        self.txt_fy = _numero("fy acero (MPa)", "420", tercio)
        self.txt_perdida = _numero("Pérdida de acero por corrosión (%)", "0", tercio)
        self.txt_luz = _numero("Luz de la viga L (m)", "", tercio)
        self.txt_cm = _numero("Carga muerta adicional D (kN/m)", "", tercio)
        self.txt_cv = _numero("Carga viva L (kN/m)", "", tercio)
        self.capas = []                       # dicts con los campos n, diametro, y y la fila
        self.filas_capas = ft.Column(spacing=6)
        self._crear_capas([None])

        extra = {"fill_color": es.AZUL} if _acepta(ft.Checkbox, "fill_color") else {}
        self.chk = ft.Checkbox(label="Evaluar a flexión (NSR-10)", value=True,
                               on_change=self._cambiar, **extra)
        self.bloque = ft.Column(spacing=10, controls=self._contenido())
        self.control = ft.Column(spacing=10, controls=[
            es.etiqueta_seccion("Acero de refuerzo y cargas", es.SUAVE_ENTRADA),
            self.chk, self.bloque])

    def _contenido(self):
        """Controles del bloque que se oculta al desmarcar la casilla."""
        texto_suave = dict(size=11.5, color=es.SUAVE_ENTRADA)
        return [
            ft.ResponsiveRow([self.txt_fc, self.txt_fy, self.txt_perdida],
                             spacing=10, run_spacing=10),
            ft.Row([_encabezado("Barras", 2), _encabezado("Ø (mm)", 2),
                    _encabezado("y desde la base (m)", 3), ft.Container(width=40)]),
            self.filas_capas,
            ft.Row(wrap=True, controls=[
                boton("Agregar capa", self._on_agregar_capa, ft.Icons.ADD, "text",
                      style=es.estilo_boton(None, es.SOBRE_ENTRADA)),
                ft.Text(AYUDA_DIAMETROS, **texto_suave)]),
            ft.ResponsiveRow([self.txt_luz, self.txt_cm, self.txt_cv],
                             spacing=10, run_spacing=10),
            ft.Text(AYUDA_CARGAS, **texto_suave),
        ]

    # ------------------------------------------------------------------ capas
    def _crear_capas(self, capas):
        """(Re)crea las filas de capas. ``capas``: lista de flexion.Capa o None (fila vacía)."""
        self.capas = []
        self.filas_capas.controls = []
        for capa in capas:
            self._agregar_fila(capa)

    def _agregar_fila(self, capa=None):
        campos = dict(
            n=_numero(None, f"{capa.n_barras}" if capa else "", expand=2),
            diametro=_numero(None, f"{capa.diametro_mm:g}" if capa else "", expand=2),
            y=_numero(None, f"{capa.y:g}" if capa else "", expand=3),
        )
        fila = ft.Row(vertical_alignment=ft.CrossAxisAlignment.START, spacing=8)
        quitar = ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=es.SUAVE_ENTRADA,
                               tooltip="Quitar capa",
                               on_click=lambda e, f=fila: self._quitar_fila(f))
        fila.controls = [campos["n"], campos["diametro"], campos["y"], quitar]
        campos["fila"] = fila
        self.capas.append(campos)
        self.filas_capas.controls.append(fila)

    def _on_agregar_capa(self, e):
        self._agregar_fila()
        self.page.update()

    def _quitar_fila(self, fila):
        self.capas = [c for c in self.capas if c["fila"] is not fila]
        self.filas_capas.controls = [c["fila"] for c in self.capas]
        if not self.capas:
            self._agregar_fila()
        self.page.update()

    def _cambiar(self, e):
        self.bloque.visible = bool(self.chk.value)
        self.page.update()

    # ------------------------------------------------------------------ datos
    def llenar(self, datos):
        """Pone en el formulario un DatosFlexion; con None desactiva la flexión."""
        self.chk.value = self.bloque.visible = datos is not None
        if datos is None:
            return
        for campo, valor in ((self.txt_fc, datos.fc), (self.txt_fy, datos.fy),
                             (self.txt_perdida, datos.perdida_acero), (self.txt_luz, datos.luz),
                             (self.txt_cm, datos.carga_muerta), (self.txt_cv, datos.carga_viva)):
            campo.value, campo.error_text = f"{valor:g}", None
        self._crear_capas(datos.capas)

    def limpiar(self):
        """Borra la luz, las cargas y las capas (deja f'c, fy y la pérdida)."""
        for campo in (self.txt_luz, self.txt_cm, self.txt_cv):
            campo.value, campo.error_text = "", None
        self._crear_capas([None])

    def leer(self, errores):
        """Valida y devuelve un DatosFlexion, o None si la flexión está desactivada.

        Los errores se agregan a ``errores`` y los campos se marcan en rojo.
        """
        if not self.chk.value:
            return None
        valores = self._leer_materiales_y_cargas(errores)
        capas = self._leer_capas(errores)
        return flexion.DatosFlexion(capas=capas, **valores)

    def _leer_materiales_y_cargas(self, errores):
        valores = {}
        for clave, campo, etiqueta, obligatorio in (
            ("fc", self.txt_fc, "f'c", True), ("fy", self.txt_fy, "fy", True),
            ("perdida_acero", self.txt_perdida, "Pérdida de acero", False),
            ("luz", self.txt_luz, "Luz de la viga", True),
            ("carga_muerta", self.txt_cm, "Carga muerta", False),
            ("carga_viva", self.txt_cv, "Carga viva", False),
        ):
            # f'c, fy y la luz deben ser > 0; la pérdida y las cargas pueden ser 0
            valor, error = leer_numero(campo.value, positivo=obligatorio, obligatorio=obligatorio)
            if error is None and valor is not None and valor < 0:
                error = "No puede ser negativo"
            if error is None and clave == "perdida_acero" and (valor or 0) >= 100:
                error = "Debe ser menor que 100"
            es.marcar_campo(campo, error, etiqueta, errores)
            valores[clave] = valor or 0.0
        return valores

    def _leer_capas(self, errores):
        capas = []
        for i, fila in enumerate(self.capas, start=1):
            n, e_n = leer_numero(fila["n"].value)
            if e_n is None and n != int(n):
                e_n = "Debe ser un número entero"
            diametro, e_d = leer_numero(fila["diametro"].value)
            y, e_y = leer_numero(fila["y"].value)
            es.marcar_campo(fila["n"], e_n, f"Capa {i}, barras", errores)
            es.marcar_campo(fila["diametro"], e_d, f"Capa {i}, Ø", errores)
            es.marcar_campo(fila["y"], e_y, f"Capa {i}, y", errores)
            if not (e_n or e_d or e_y):
                capas.append(flexion.Capa(int(n), diametro, y))
        return capas


# ---------------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------------
def resultados_flexion(f):
    """Controles del chequeo a flexión: (aviso, indicadores) y (figura, tabla).

    Devuelve dos listas para que la vista las ubique antes y después de la parte
    geométrica.
    """
    return [_aviso(f), _indicadores(f)], [_figura(f.modificada), _detalle(f)]


def _aviso(f):
    mod = f.modificada
    color, fondo, _ = es.SEVERIDAD["VERDE" if mod.cumple else "ROJO"]
    return ft.Container(
        padding=18, border_radius=14, bgcolor=fondo, border=es.borde(1, color),
        content=ft.Row(spacing=16, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
            ft.Icon(ft.Icons.STRAIGHTEN, color=color, size=44),
            ft.Column(spacing=2, expand=True, controls=[
                ft.Text("Chequeo a flexión NSR-10 · sección inspeccionada", size=13,
                        color=color, weight=ft.FontWeight.W_600),
                ft.Text(f"φMn = {mod.phi_mn:,.1f} kN·m   vs   Mu = {mod.mu:,.1f} kN·m",
                        size=20, weight=ft.FontWeight.BOLD, color=es.TEXTO),
                ft.Text(f"Mu / φMn = {mod.relacion:.2f}  ·  {f.texto_vida()}", size=13,
                        color=es.TEXTO_SUAVE),
            ]),
            es.chip("CUMPLE" if mod.cumple else "NO CUMPLE", es.TARJETA, color),
        ]),
    )


def _indicadores(f):
    def color(r):
        return es.SEVERIDAD["VERDE" if r.cumple else "ROJO"][0]

    i, m, col = f.ideal, f.modificada, {"xs": 6, "md": 3}
    return ft.ResponsiveRow(spacing=12, run_spacing=12, controls=[
        es.indicador("φMn sección ideal", f"{i.phi_mn:,.0f}", "kN·m", color(i), col,
                     detalle=f"Mu/φMn = {i.relacion:.2f}"),
        es.indicador("φMn sección inspeccionada", f"{m.phi_mn:,.0f}", "kN·m", color(m), col,
                     detalle=f"Pierde {f.perdida_phi_mn:.1f} %"),
        es.indicador("Momento último Mu", f"{m.mu:,.0f}", "kN·m", es.PRIMARIO, col,
                     detalle=f"wu = {m.wu:.1f} kN/m"),
        es.indicador("Acero inspeccionado", f"{m.as_total_mm2:,.0f}", "mm²", es.PRIMARIO, col,
                     detalle=f"−{f.datos.perdida_acero:g} % por corrosión"),
    ])


def _figura(mod):
    png = graficas.figura_a_png(graficas.figura_flexion(mod, oscuro=True))
    return es.tarjeta(
        es.titulo("Flexión de la sección inspeccionada", ft.Icons.STRAIGHTEN,
                  f"c = {mod.c * 100:.1f} cm · a = {mod.a * 100:.1f} cm · "
                  f"εt = {mod.eps_t * 1000:.1f} ‰ · φ = {mod.phi:.2f}"),
        imagen_png(png, fit=AJUSTE_CONTENER), padding=14)


# (nombre, unidad, función que saca el valor de un ResultadoFlexion, formato)
FILAS_TABLA = [
    ("Área de acero As", "mm²", lambda r: r.as_total_mm2, "{:,.0f}"),
    ("Eje neutro c", "cm", lambda r: r.c * 100, "{:,.2f}"),
    ("Bloque de Whitney a = β1·c", "cm", lambda r: r.a * 100, "{:,.2f}"),
    ("Deformación del acero extremo εt", "‰", lambda r: r.eps_t * 1000, "{:,.2f}"),
    ("Factor φ", "-", lambda r: r.phi, "{:.3f}"),
    ("Resistencia nominal Mn", "kN·m", lambda r: r.mn, "{:,.1f}"),
    ("Resistencia de diseño φMn", "kN·m", lambda r: r.phi_mn, "{:,.1f}"),
    ("Momento de agrietamiento Mcr", "kN·m", lambda r: r.mcr, "{:,.1f}"),
    ("Peso propio", "kN/m", lambda r: r.peso_propio, "{:,.2f}"),
    ("Momento último Mu", "kN·m", lambda r: r.mu, "{:,.1f}"),
    ("Mu / φMn", "-", lambda r: r.relacion, "{:.3f}"),
]


def _detalle(f):
    filas = [ft.DataRow(cells=[ft.DataCell(ft.Text(texto)) for texto in
                               (nombre, unidad, fmt.format(valor(f.ideal)),
                                fmt.format(valor(f.modificada)))])
             for nombre, unidad, valor, fmt in FILAS_TABLA]
    tabla = ft.DataTable(heading_row_color=es.PRIMARIO_CLARO, column_spacing=28, rows=filas,
                         columns=es.encabezado_tabla("Resultado", "Unidad", "Ideal",
                                                     "Inspeccionada"))
    return es.tarjeta(
        es.titulo("Resultados a flexión", ft.Icons.TABLE_CHART,
                  f"f'c = {f.datos.fc:g} MPa · fy = {f.datos.fy:g} MPa · "
                  f"β1 = {f.ideal.beta1:.3f} · L = {f.datos.luz:g} m"),
        ft.Row([tabla], scroll=ft.ScrollMode.AUTO),
        *[ft.Text(a, color=es.SEVERIDAD["NARANJA"][0], size=12.5) for a in _avisos(f.modificada)])


def _avisos(mod):
    """Advertencias de la NSR-10 que no impiden el cálculo."""
    avisos = []
    if not mod.ductil:
        avisos.append("εt < 0.004: la sección no es dúctil (NSR-10 C.10.3.5).")
    if not mod.cumple_as_min:
        avisos.append(f"As < As,mín = {mod.as_min_mm2:,.0f} mm² (NSR-10 C.10.5.1).")
    return avisos
