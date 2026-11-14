"""Gráficas técnicas con Matplotlib.

Las funciones devuelven objetos ``Figure`` (sin pyplot, para no depender de una
ventana). La interfaz las muestra como PNG y la memoria de cálculo las inserta
con ``InlineImage``: es la misma figura en ambos lugares.
"""

import io

import numpy as np
from matplotlib import rc_context
from matplotlib.figure import Figure

from app.modelo import UMBRAL_INTERVENCION, UMBRAL_PREVENTIVO

COLOR_SEVERIDAD = {"VERDE": "#2e7d32", "NARANJA": "#ef6c00", "ROJO": "#c62828"}

# Paletas: "claro" para la memoria de Word, "oscuro" para la interfaz
TEMAS = {
    False: dict(rc={}, ideal="#1565c0", principal="black", area="#6a1b9a", ixx="#00838f",
                actual="gray", severidad=COLOR_SEVERIDAD),
    True: dict(
        rc={"figure.facecolor": "#15171E", "axes.facecolor": "#1D2029",
            "axes.edgecolor": "#2A2E3A", "axes.labelcolor": "#F2F4F8",
            "axes.titlecolor": "#F2F4F8", "text.color": "#F2F4F8",
            "xtick.color": "#9AA3B2", "ytick.color": "#9AA3B2", "grid.color": "#2A2E3A",
            "legend.facecolor": "#15171E", "legend.edgecolor": "#2A2E3A",
            "legend.labelcolor": "#F2F4F8"},
        ideal="#27B0F5", principal="#FFFFFF", area="#FF005F", ixx="#B388FF",
        actual="#9AA3B2",
        severidad={"VERDE": "#4ADE80", "NARANJA": "#FFA726", "ROJO": "#FF5370"}),
}


def _cerrar(puntos):
    return np.vstack((puntos, puntos[:1]))


def figura_geometria(resultado, oscuro=False):
    """Sección ideal y modificada superpuestas, con sus ejes neutros."""
    with rc_context(TEMAS[oscuro]["rc"]):
        return _figura_geometria(resultado, TEMAS[oscuro])


def _figura_geometria(resultado, tema):
    fig = Figure(figsize=(6.4, 5.2), dpi=110, layout="constrained")
    ax = fig.add_subplot()
    color_mod = tema["severidad"][resultado.severidad]

    for puntos, props, etiqueta, color, estilo in (
        (resultado.puntos_ideal, resultado.ideal, "Sección ideal", tema["ideal"], "-"),
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


def figura_capacidad(resultado, oscuro=False):
    """Capacidad relativa (%) de A, Ixx y Zx frente al nivel de daño (o al tiempo)."""
    with rc_context(TEMAS[oscuro]["rc"]):
        return _figura_capacidad(resultado, TEMAS[oscuro])


def _figura_capacidad(resultado, tema):
    proy = resultado.proyeccion
    fig = Figure(figsize=(7.2, 4.6), dpi=110, layout="constrained")
    ax = fig.add_subplot()

    usar_tiempo = bool(proy.edad_anios)
    eje = proy.alfa * proy.edad_anios if usar_tiempo else proy.alfa
    actual = proy.edad_anios if usar_tiempo else 1.0

    ax.plot(eje, proy.capacidad_area, color=tema["area"], label="Área A")
    ax.plot(eje, proy.capacidad_ixx, color=tema["ixx"], label="Inercia Ixx")
    ax.plot(eje, proy.capacidad_zx, color=tema["principal"], linewidth=2.2,
            label="Módulo resistente Zx")

    for umbral, color in ((UMBRAL_PREVENTIVO, tema["severidad"]["NARANJA"]),
                          (UMBRAL_INTERVENCION, tema["severidad"]["ROJO"])):
        nivel = 100 - umbral
        ax.axhline(nivel, color=color, linestyle="--", linewidth=1,
                   label=f"Umbral {umbral:.0f} % de pérdida de Zx ({nivel:.0f} %)")
        a = proy.alfa_umbral.get(umbral)
        if a is not None:
            x = a * proy.edad_anios if usar_tiempo else a
            ax.plot([x], [nivel], "o", color=color, zorder=5)
            ax.annotate(f"{x:.1f} años" if usar_tiempo else f"α = {x:.2f}", (x, nivel),
                        textcoords="offset points", xytext=(6, 6), fontsize=8, color=color)

    ax.axvline(actual, color=tema["actual"], linewidth=1, linestyle="-.",
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
    figura.savefig(buffer, format="png", facecolor=figura.get_facecolor())
    return buffer.getvalue()


def guardar_figura(figura, ruta):
    figura.savefig(ruta, format="png", facecolor=figura.get_facecolor())
    return ruta
