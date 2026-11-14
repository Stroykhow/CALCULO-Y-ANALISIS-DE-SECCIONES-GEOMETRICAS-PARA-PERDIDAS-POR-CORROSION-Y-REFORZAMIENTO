"""Pequeñas funciones de ayuda para Flet.

Flet cambió algunos nombres entre la serie 0.2x y la 1.x (``page.open`` →
``page.show_dialog``, ``text=`` → ``content=`` en botones, ``src_base64`` →
``src``). Estas funciones aíslan esas diferencias para que el resto de la
interfaz funcione con cualquiera de las dos versiones.
"""

import base64
import inspect

import flet as ft


def _acepta(clase, parametro):
    """True si el constructor de la clase de Flet tiene ese parámetro."""
    try:
        return parametro in inspect.signature(clase).parameters
    except (TypeError, ValueError):
        return False


def ejecutar(funcion_principal):
    """Arranca la aplicación (ft.run en Flet 1.x, ft.app en 0.2x)."""
    if hasattr(ft, "run"):
        ft.run(funcion_principal)
    else:
        ft.app(target=funcion_principal)


def boton(texto, on_click=None, icono=None, tipo="filled", **kwargs):
    """Botón con texto. tipo: 'filled', 'outlined' o 'text'."""
    clase = {"filled": ft.FilledButton, "outlined": ft.OutlinedButton,
             "text": ft.TextButton}[tipo]
    if _acepta(clase, "text"):            # Flet 0.2x
        return clase(text=texto, icon=icono, on_click=on_click, **kwargs)
    return clase(content=texto, icon=icono, on_click=on_click, **kwargs)   # Flet 1.x


def abrir(page, control):
    """Muestra un diálogo o un SnackBar."""
    if hasattr(page, "show_dialog"):
        page.show_dialog(control)
    else:
        page.open(control)


def cerrar(page, control):
    """Cierra un diálogo abierto con ``abrir``."""
    for metodo in ("pop_dialog", "close_dialog"):   # Flet 1.x
        if hasattr(page, metodo):
            getattr(page, metodo)()
            return
    page.close(control)                          # Flet 0.2x


def avisar(page, mensaje, error=False):
    """Retroalimentación de una acción con un SnackBar."""
    barra = ft.SnackBar(
        content=ft.Text(mensaje, color=ft.Colors.WHITE),
        bgcolor=ft.Colors.RED_700 if error else ft.Colors.GREEN_700,
    )
    abrir(page, barra)


def imagen_png(png, **kwargs):
    """Control Image a partir de bytes PNG."""
    if _acepta(ft.Image, "src_base64"):   # Flet 0.2x
        return ft.Image(src_base64=base64.b64encode(png).decode("ascii"), **kwargs)
    return ft.Image(src=png, **kwargs)    # Flet 1.x acepta bytes en src
