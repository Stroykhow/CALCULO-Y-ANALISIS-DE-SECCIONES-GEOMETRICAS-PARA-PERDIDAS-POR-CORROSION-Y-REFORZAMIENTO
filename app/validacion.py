"""Validación de entradas de texto (independiente de la interfaz)."""

import math


def leer_numero(texto, positivo=True, obligatorio=True):
    """Convierte el texto de un campo a float.

    Acepta coma o punto decimal. Devuelve ``(valor, mensaje_error)``; si el
    texto es válido, ``mensaje_error`` es None. Un campo opcional vacío
    devuelve ``(None, None)``.
    """
    texto = (texto or "").strip().replace(",", ".")
    if not texto:
        return None, ("Campo obligatorio" if obligatorio else None)
    try:
        valor = float(texto)
    except ValueError:
        return None, "Debe ser un número"
    if not math.isfinite(valor):
        return None, "Debe ser un número finito"
    if positivo and valor <= 0:
        return None, "Debe ser mayor que 0"
    return valor, None
