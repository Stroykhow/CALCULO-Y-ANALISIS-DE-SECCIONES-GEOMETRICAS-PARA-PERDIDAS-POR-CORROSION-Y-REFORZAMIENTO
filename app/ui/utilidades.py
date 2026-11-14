"""Funciones compartidas por las vistas de Flet."""

import os
import subprocess
import sys

import flet as ft

from app import db, reporte
from app.ui.compat import avisar

COLOR_SEVERIDAD = {"VERDE": ft.Colors.GREEN_700, "NARANJA": ft.Colors.ORANGE_800,
                   "ROJO": ft.Colors.RED_700}


def abrir_archivo(ruta):
    """Abre un archivo con el programa predeterminado del sistema (Word)."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(ruta)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(ruta)])
        else:
            subprocess.Popen(["xdg-open", str(ruta)])
    except OSError:
        pass  # si no hay programa asociado, el aviso ya muestra la ruta


def generar_y_abrir_memoria(page, conexion, calculo_id, autores=""):
    """Genera la memoria .docx de un cálculo guardado, avisa y la abre."""
    calculo = db.obtener_calculo(conexion, calculo_id)
    if calculo is None:
        avisar(page, "El cálculo ya no existe en la base de datos.", error=True)
        return None
    try:
        ruta = reporte.generar_memoria(calculo, autores=autores)
    except PermissionError:
        avisar(page, "No se pudo escribir la memoria: ciérrela en Word e intente de nuevo.",
               error=True)
        return None
    except Exception as error:  # noqa: BLE001 — se informa al usuario sin cerrar la app
        avisar(page, f"Error al generar la memoria: {error}", error=True)
        return None
    avisar(page, f"Memoria generada: {ruta}")
    abrir_archivo(ruta)
    return ruta
