"""Paleta y componentes visuales reutilizables (tarjetas, títulos, indicadores)."""

import flet as ft

# Colores tomados del ícono de la aplicación
ROSA = "#FF005F"
AZUL = "#27B0F5"

# Tema oscuro
FONDO = "#0A0A0F"          # fondo de la ventana
TARJETA = "#15171E"        # superficie de las tarjetas de resultados
SUPERFICIE_2 = "#1D2029"   # encabezados de tabla, estados vacíos
BORDE = "#2A2E3A"
TEXTO = "#F2F4F8"
TEXTO_SUAVE = "#9AA3B2"
TEXTO_OSCURO = "#06121C"   # texto sobre el azul del encabezado

PRIMARIO = AZUL            # color de acento (íconos y títulos)
PRIMARIO_CLARO = SUPERFICIE_2

def borde(ancho=1, color=BORDE):
    """Borde uniforme (ft.Border.all en Flet 1.x, ft.border.all en 0.2x)."""
    clase = getattr(ft, "Border", None)
    if clase is not None and hasattr(clase, "all"):
        return clase.all(ancho, color)
    return ft.border.all(ancho, color)


def relleno(horizontal, vertical):
    """Padding simétrico (ft.Padding.symmetric en Flet 1.x, ft.padding en 0.2x)."""
    clase = getattr(ft, "Padding", None)
    if clase is not None and hasattr(clase, "symmetric"):
        return clase.symmetric(horizontal=horizontal, vertical=vertical)
    return ft.padding.symmetric(horizontal=horizontal, vertical=vertical)


SEVERIDAD = {
    # color fuerte, fondo suave, ícono
    "VERDE": ("#4ADE80", "#0F2A1A", ft.Icons.CHECK_CIRCLE),
    "NARANJA": ("#FFA726", "#2E1D08", ft.Icons.WARNING_AMBER),
    "ROJO": ("#FF5370", "#33101A", ft.Icons.DANGEROUS),
}


def tarjeta(*controles, col=None, padding=20, expand=False, spacing=14, bgcolor=TARJETA,
            color_borde=BORDE, sombra="#66000000"):
    """Contenedor con bordes redondeados y sombra suave."""
    return ft.Container(
        col=col, expand=expand, padding=padding, bgcolor=bgcolor, border_radius=16,
        border=borde(1, color_borde),
        shadow=ft.BoxShadow(blur_radius=18, spread_radius=0, color=sombra,
                            offset=ft.Offset(0, 4)),
        content=ft.Column(list(controles), spacing=spacing, tight=True),
    )


def titulo(texto, icono=None, subtitulo=None, color=TEXTO, acento=PRIMARIO,
           color_sub=TEXTO_SUAVE):
    """Encabezado de una tarjeta."""
    fila = [ft.Icon(icono, color=acento, size=22)] if icono else []
    fila.append(ft.Text(texto, size=17, weight=ft.FontWeight.W_600, color=color))
    controles = [ft.Row(fila, spacing=8)]
    if subtitulo:
        controles.append(ft.Text(subtitulo, size=12.5, color=color_sub))
    return ft.Column(controles, spacing=2, tight=True)


def etiqueta_seccion(texto, color=TEXTO_SUAVE):
    return ft.Text(texto.upper(), size=11.5, weight=ft.FontWeight.W_600, color=color)


def indicador(nombre, valor, unidad="%", color=PRIMARIO, col=None, detalle=None):
    """Tarjeta pequeña con un número grande (KPI)."""
    controles = [
        ft.Text(nombre, size=12.5, color=TEXTO_SUAVE),
        ft.Row([ft.Text(valor, size=26, weight=ft.FontWeight.BOLD, color=color),
                ft.Text(unidad, size=14, color=TEXTO_SUAVE)],
               spacing=4, vertical_alignment=ft.CrossAxisAlignment.END),
    ]
    if detalle:
        controles.append(ft.Text(detalle, size=11.5, color=TEXTO_SUAVE))
    return ft.Container(
        col=col, padding=14, bgcolor=TARJETA, border_radius=12,
        border=borde(),
        content=ft.Column(controles, spacing=2, tight=True),
    )


def chip(texto, color, fondo):
    return ft.Container(
        padding=relleno(10, 3),
        border_radius=20, bgcolor=fondo,
        content=ft.Text(texto, size=12, weight=ft.FontWeight.W_600, color=color),
    )


def estado_vacio(icono, texto, detalle=""):
    return ft.Container(
        padding=40, border_radius=16, bgcolor=TARJETA, border=borde(1, BORDE),
        content=ft.Column(
            [ft.Icon(icono, size=48, color=PRIMARIO),
             ft.Text(texto, size=16, weight=ft.FontWeight.W_600, color=TEXTO,
                     text_align=ft.TextAlign.CENTER),
             ft.Text(detalle, size=13, color=TEXTO_SUAVE, text_align=ft.TextAlign.CENTER)],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8, tight=True),
    )


# ---------------------------------------------------------------------------
# Tarjeta de datos de entrada (azul marino con acentos celestes)
# ---------------------------------------------------------------------------
FONDO_ENTRADA = "#0F2A44"
BORDE_ENTRADA = "#1F4A70"
SOBRE_ENTRADA = "#FFFFFF"
SUAVE_ENTRADA = "#9FD8F7"
ROJO_ERROR = "#FF5252"
BORDE_CAMPO = "#8CFFFFFF"


def estilo_campo():
    """Estilo de los TextField sobre la tarjeta de entrada (solo opciones que existan)."""
    from app.ui.compat import _acepta
    estilo = dict(
        filled=True, bgcolor="#33000000", border_color=BORDE_CAMPO,
        focused_border_color=AZUL, color=SOBRE_ENTRADA, cursor_color=SOBRE_ENTRADA,
        label_style=ft.TextStyle(color=SUAVE_ENTRADA),
        hint_style=ft.TextStyle(color="#99FFFFFF"),
        error_style=ft.TextStyle(color="#FFF176", weight=ft.FontWeight.W_600),
    )
    return {k: v for k, v in estilo.items() if _acepta(ft.TextField, k)}


def marcar_campo(campo, error, etiqueta, errores):
    """Marca un campo en rojo si tiene error y agrega el mensaje a la lista ``errores``."""
    campo.error_text = error
    campo.border_color = ROJO_ERROR if error else BORDE_CAMPO
    campo.focused_border_color = ROJO_ERROR if error else AZUL
    if error:
        errores.append(f"{etiqueta}: {error}")


def estilo_boton(fondo, texto, borde=None):
    """ButtonStyle con fondo, color de texto y, si se pide, un borde."""
    lado = {"side": ft.BorderSide(1.5, borde)} if borde else {}
    return ft.ButtonStyle(bgcolor=fondo, color=texto, **lado)


def encabezado_tabla(*titulos):
    """Columnas de una DataTable con los títulos en negrita."""
    return [ft.DataColumn(ft.Text(t, weight=ft.FontWeight.W_600)) for t in titulos]
