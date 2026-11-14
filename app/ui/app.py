"""Ventana principal: barra de navegación entre las vistas Cálculo e Historial."""

import flet as ft

from app import db
from app.ui.compat import boton
from app.ui.vista_calculo import VistaCalculo
from app.ui.vista_historial import VistaHistorial

TITULO = "Bridge Section Analyzer — Pérdida por corrosión y reforzamiento"


def main(page: ft.Page):
    page.title = TITULO
    page.padding = 16
    try:
        page.window.width, page.window.height = 1350, 900
    except AttributeError:
        pass

    conexion = db.conectar()          # crea datos/proyectos.db si no existe
    cuerpo = ft.Container(expand=True)
    barra = ft.Row()

    def ir_a(nombre):
        cuerpo.content = vistas[nombre].control
        if nombre == "historial":
            historial.refrescar(actualizar=False)
        barra.controls = [
            boton("Cálculo", lambda e: ir_a("calculo"), ft.Icons.CALCULATE,
                  "filled" if nombre == "calculo" else "outlined"),
            boton("Historial", lambda e: ir_a("historial"), ft.Icons.HISTORY,
                  "filled" if nombre == "historial" else "outlined"),
        ]
        page.update()

    def reabrir(calculo):
        ir_a("calculo")
        calculo_vista.cargar_calculo(calculo)

    calculo_vista = VistaCalculo(page, conexion)
    historial = VistaHistorial(page, conexion, al_abrir=reabrir, autores=calculo_vista.autores)
    vistas = {"calculo": calculo_vista, "historial": historial}

    page.add(
        ft.Row([ft.Icon(ft.Icons.ARCHITECTURE, size=30),
                ft.Text(TITULO, size=22, weight=ft.FontWeight.BOLD)]),
        barra,
        ft.Divider(height=1),
        cuerpo,
    )
    ir_a("calculo")
