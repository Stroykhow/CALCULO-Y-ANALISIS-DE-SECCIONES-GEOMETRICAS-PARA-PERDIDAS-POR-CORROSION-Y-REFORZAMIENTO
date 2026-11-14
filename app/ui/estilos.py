"""Paleta y componentes visuales reutilizables (tarjetas, títulos, indicadores)."""

import flet as ft

PRIMARIO = "#0D3B66"
PRIMARIO_CLARO = "#E8EEF6"
FONDO = "#F3F5F9"
TARJETA = "#FFFFFF"
BORDE = "#DDE3EC"
TEXTO = "#1F2933"
TEXTO_SUAVE = "#61707F"

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
    "VERDE": ("#2E7D32", "#E8F5E9", ft.Icons.CHECK_CIRCLE),
    "NARANJA": ("#E65100", "#FFF3E0", ft.Icons.WARNING_AMBER),
    "ROJO": ("#C62828", "#FFEBEE", ft.Icons.DANGEROUS),
}


def tarjeta(*controles, col=None, padding=20, expand=False, spacing=14):
    """Contenedor blanco con bordes redondeados y sombra suave."""
    return ft.Container(
        col=col, expand=expand, padding=padding, bgcolor=TARJETA, border_radius=14,
        border=borde(),
        shadow=ft.BoxShadow(blur_radius=14, spread_radius=0, color="#140D3B66",
                            offset=ft.Offset(0, 3)),
        content=ft.Column(list(controles), spacing=spacing, tight=True),
    )


def titulo(texto, icono=None, subtitulo=None):
    """Encabezado de una tarjeta."""
    fila = [ft.Icon(icono, color=PRIMARIO, size=22)] if icono else []
    fila.append(ft.Text(texto, size=17, weight=ft.FontWeight.W_600, color=TEXTO))
    controles = [ft.Row(fila, spacing=8)]
    if subtitulo:
        controles.append(ft.Text(subtitulo, size=12.5, color=TEXTO_SUAVE))
    return ft.Column(controles, spacing=2, tight=True)


def etiqueta_seccion(texto):
    return ft.Text(texto.upper(), size=11.5, weight=ft.FontWeight.W_600, color=TEXTO_SUAVE)


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
        padding=40, border_radius=14, bgcolor=PRIMARIO_CLARO,
        content=ft.Column(
            [ft.Icon(icono, size=48, color=PRIMARIO),
             ft.Text(texto, size=16, weight=ft.FontWeight.W_600, color=TEXTO,
                     text_align=ft.TextAlign.CENTER),
             ft.Text(detalle, size=13, color=TEXTO_SUAVE, text_align=ft.TextAlign.CENTER)],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8, tight=True),
    )
