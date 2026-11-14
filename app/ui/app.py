"""Ventana principal: encabezado con navegación entre las vistas Cálculo e Historial."""

import flet as ft

from app import db
from app.ui import estilos as es
from app.ui.vista_calculo import VistaCalculo
from app.ui.vista_historial import VistaHistorial

TITULO = "Bridge Section Analyzer"
SUBTITULO = "Pérdida de sección por corrosión y reforzamiento"


def _pestana(texto, icono, activa, on_click):
    """Botón de navegación tipo píldora para el encabezado azul."""
    color = "#FFFFFF" if activa else es.TEXTO_OSCURO
    return ft.Container(
        on_click=on_click, border_radius=22, padding=es.relleno(16, 8),
        bgcolor=es.FONDO if activa else "#33FFFFFF",
        content=ft.Row([ft.Icon(icono, color=color, size=18),
                        ft.Text(texto, color=color, weight=ft.FontWeight.W_600)],
                       spacing=6, tight=True),
    )


def main(page: ft.Page):
    page.title = f"{TITULO} — {SUBTITULO}"
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(color_scheme_seed=es.AZUL)
    page.dark_theme = ft.Theme(color_scheme_seed=es.AZUL)
    page.bgcolor = es.FONDO
    page.padding = 0
    try:
        page.window.width, page.window.height = 1400, 900
        page.window.min_width, page.window.min_height = 420, 600
    except AttributeError:
        pass

    conexion = db.conectar()          # crea datos/proyectos.db si no existe
    cuerpo = ft.Container(expand=True, padding=20)
    navegacion = ft.Row(spacing=8, tight=True)

    encabezado = ft.Container(
        bgcolor=es.AZUL, padding=es.relleno(24, 14),
        content=ft.ResponsiveRow(
            vertical_alignment=ft.CrossAxisAlignment.CENTER, run_spacing=10,
            controls=[
                ft.Row(col={"xs": 12, "md": 7}, spacing=12, controls=[
                    ft.Container(
                        bgcolor=es.ROSA, border_radius=12, padding=8,
                        content=ft.Icon(ft.Icons.ARCHITECTURE, color="#FFFFFF", size=28)),
                    ft.Column(spacing=0, tight=True, controls=[
                        ft.Text(TITULO, size=20, weight=ft.FontWeight.BOLD,
                                color=es.TEXTO_OSCURO),
                        ft.Text(SUBTITULO, size=12.5, color="#0B3B57"),
                    ]),
                ]),
                ft.Row([navegacion], col={"xs": 12, "md": 5},
                       alignment=ft.MainAxisAlignment.END),
            ]),
    )

    def ir_a(nombre):
        cuerpo.content = vistas[nombre].control
        if nombre == "historial":
            historial.refrescar(actualizar=False)
        navegacion.controls = [
            _pestana("Cálculo", ft.Icons.CALCULATE, nombre == "calculo",
                     lambda e: ir_a("calculo")),
            _pestana("Historial", ft.Icons.HISTORY, nombre == "historial",
                     lambda e: ir_a("historial")),
        ]
        page.update()

    def reabrir(calculo):
        ir_a("calculo")
        calculo_vista.cargar_calculo(calculo)

    calculo_vista = VistaCalculo(page, conexion)
    historial = VistaHistorial(page, conexion, al_abrir=reabrir, autores=calculo_vista.autores)
    vistas = {"calculo": calculo_vista, "historial": historial}

    page.add(ft.Column([encabezado, cuerpo], expand=True, spacing=0))
    ir_a("calculo")
