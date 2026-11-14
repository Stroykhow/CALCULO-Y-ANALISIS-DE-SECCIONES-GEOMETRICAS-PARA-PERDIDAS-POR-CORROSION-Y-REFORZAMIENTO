"""Gráficas técnicas con Matplotlib.

Las funciones devuelven objetos ``Figure`` (sin pyplot, para no depender de una
ventana). La interfaz las muestra como PNG y la memoria de cálculo las inserta
con ``InlineImage``: es la misma figura en ambos lugares.
"""

import io

import numpy as np
from matplotlib.figure import Figure

from app.modelo import UMBRAL_INTERVENCION, UMBRAL_PREVENTIVO

COLOR_SEVERIDAD = {"VERDE": "#2e7d32", "NARANJA": "#ef6c00", "ROJO": "#c62828"}


def _cerrar(puntos):
    return np.vstack((puntos, puntos[:1]))


def figura_geometria(resultado):
    """Sección ideal y modificada superpuestas, con sus ejes neutros."""
    fig = Figure(figsize=(6.4, 5.2), dpi=110, layout="constrained")
    ax = fig.add_subplot()
    color_mod = COLOR_SEVERIDAD[resultado.severidad]

    for puntos, props, etiqueta, color, estilo in (
        (resultado.puntos_ideal, resultado.ideal, "Sección ideal", "#1565c0", "-"),
        (resultado.puntos_mod, resultado.modificada, "Sección modificada", color_mod, "--"),
    ):
        p = _cerrar(puntos)
        ax.plot(p[:, 0], p[:, 1], estilo, color=color, linewidth=1.6, label=etiqueta)
        ax.fill(p[:, 0], p[:, 1], color=color, alpha=0.12)
        ax.axhline(props["yc"], color=color, linestyle=":", linewidth=1.2,
                   label=f"Eje neutro {etiqueta.split()[-1]}: yc = {props['yc']:.4f} m")

    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title("Geometría de la sección transversal")
    ax.legend(loc="best", fontsize=8)
    return fig


def figura_capacidad(resultado):
    """Capacidad relativa (%) de A, Ixx y Zx frente al nivel de daño (o al tiempo)."""
    proy = resultado.proyeccion
    fig = Figure(figsize=(7.2, 4.6), dpi=110, layout="constrained")
    ax = fig.add_subplot()

    usar_tiempo = bool(proy.edad_anios)
    eje = proy.alfa * proy.edad_anios if usar_tiempo else proy.alfa
    actual = proy.edad_anios if usar_tiempo else 1.0

    ax.plot(eje, proy.capacidad_area, color="#6a1b9a", label="Área A")
    ax.plot(eje, proy.capacidad_ixx, color="#00838f", label="Inercia Ixx")
    ax.plot(eje, proy.capacidad_zx, color="black", linewidth=2.2, label="Módulo resistente Zx")

    for umbral, color in ((UMBRAL_PREVENTIVO, COLOR_SEVERIDAD["NARANJA"]),
                          (UMBRAL_INTERVENCION, COLOR_SEVERIDAD["ROJO"])):
        nivel = 100 - umbral
        ax.axhline(nivel, color=color, linestyle="--", linewidth=1,
                   label=f"Umbral {umbral:.0f} % de pérdida de Zx ({nivel:.0f} %)")
        a = proy.alfa_umbral.get(umbral)
        if a is not None:
            x = a * proy.edad_anios if usar_tiempo else a
            ax.plot([x], [nivel], "o", color=color, zorder=5)
            ax.annotate(f"{x:.1f} años" if usar_tiempo else f"α = {x:.2f}", (x, nivel),
                        textcoords="offset points", xytext=(6, 6), fontsize=8, color=color)

    ax.axvline(actual, color="gray", linewidth=1, linestyle="-.",
               label="Estado inspeccionado")
    ax.set_xlabel("Tiempo desde la construcción (años)" if usar_tiempo
                  else "Nivel de daño α (0 = ideal, 1 = inspeccionado) (-)")
    ax.set_ylabel("Capacidad relativa a la sección ideal (%)")
    ax.set_title("Proyección de la pérdida de capacidad (avance lineal del daño)")
    ax.set_xlim(eje[0], eje[-1])
    ax.legend(loc="best", fontsize=7)
    return fig


def figura_a_png(figura):
    """Convierte una figura en bytes PNG."""
    buffer = io.BytesIO()
    figura.savefig(buffer, format="png")
    return buffer.getvalue()


def guardar_figura(figura, ruta):
    figura.savefig(ruta, format="png")
    return ruta
