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
                actual="gray", severidad=COLOR_SEVERIDAD, resistencia="#2e7d32",
                demanda="#c62828", acero="#455a64", compresion="#1565c0"),
    True: dict(
        rc={"figure.facecolor": "#15171E", "axes.facecolor": "#1D2029",
            "axes.edgecolor": "#2A2E3A", "axes.labelcolor": "#F2F4F8",
            "axes.titlecolor": "#F2F4F8", "text.color": "#F2F4F8",
            "xtick.color": "#9AA3B2", "ytick.color": "#9AA3B2", "grid.color": "#2A2E3A",
            "legend.facecolor": "#15171E", "legend.edgecolor": "#2A2E3A",
            "legend.labelcolor": "#F2F4F8"},
        ideal="#27B0F5", principal="#FFFFFF", area="#FF005F", ixx="#B388FF",
        actual="#9AA3B2",
        severidad={"VERDE": "#4ADE80", "NARANJA": "#FFA726", "ROJO": "#FF5370"},
        resistencia="#4ADE80", demanda="#FF5370", acero="#CFD8DC", compresion="#27B0F5"),
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

    flex = resultado.flexion
    if flex is not None:
        eje_f = flex.alfa * proy.edad_anios if usar_tiempo else flex.alfa
        ax.plot(eje_f, flex.phi_mn_pct, color=tema["resistencia"], linewidth=2.2,
                label="Resistencia a flexión φMn")
        ax.plot(eje_f, flex.mu_pct, color=tema["demanda"], linewidth=1.4, linestyle=(0, (6, 3)),
                label="Demanda Mu")
        if flex.alfa_falla:
            x = flex.alfa_falla * proy.edad_anios if usar_tiempo else flex.alfa_falla
            y = float(np.interp(flex.alfa_falla, flex.alfa, flex.mu_pct))
            ax.plot([x], [y], "X", color=tema["demanda"], markersize=9, zorder=6)
            ax.annotate(f"φMn < Mu: {x:.1f} años" if usar_tiempo else f"φMn < Mu: α = {x:.2f}",
                        (x, y), textcoords="offset points", xytext=(8, -14), fontsize=8,
                        color=tema["demanda"])

    ax.axvline(actual, color=tema["actual"], linewidth=1, linestyle="-.",
               label="Estado inspeccionado")
    ax.set_xlabel("Tiempo desde la construcción (años)" if usar_tiempo
                  else "Nivel de daño α (0 = ideal, 1 = inspeccionado) (-)")
    ax.set_ylabel("Capacidad relativa a la sección ideal (%)")
    ax.set_title("Proyección de la pérdida de capacidad (avance lineal del daño)")
    ax.set_xlim(eje[0], eje[-1])
    ax.legend(loc="best", fontsize=7)
    return fig


def figura_flexion(resultado_flexion, oscuro=False, titulo="Sección modificada"):
    """Sección con barras, bloque de compresión y diagrama de deformaciones."""
    with rc_context(TEMAS[oscuro]["rc"]):
        return _figura_flexion(resultado_flexion, TEMAS[oscuro], titulo)


def _limites_en(puntos, y):
    """x mínimo y máximo del polígono a la altura y (donde la recta y corta sus lados)."""
    P = np.asarray(puntos)
    A, B = P, np.roll(P, -1, axis=0)
    cruza = (A[:, 1] - y) * (B[:, 1] - y) <= 0
    cruza &= A[:, 1] != B[:, 1]
    t = (y - A[cruza, 1]) / (B[cruza, 1] - A[cruza, 1])
    xs = A[cruza, 0] + t * (B[cruza, 0] - A[cruza, 0])
    return (float(xs.min()), float(xs.max())) if len(xs) else (-0.1, 0.1)


def _figura_flexion(r, tema, titulo):
    fig = Figure(figsize=(7.6, 4.8), dpi=110, layout="constrained")
    ax, ax_def = fig.subplots(1, 2, gridspec_kw={"width_ratios": [1.5, 1]}, sharey=True)
    _dibujar_seccion(ax, r, tema, titulo)
    _dibujar_deformaciones(ax_def, r, tema)
    return fig


def _color_barra(capa, tema):
    return tema["resistencia"] if capa["fluye"] else tema["severidad"]["NARANJA"]


def _dibujar_seccion(ax, r, tema, titulo):
    """Contorno, bloque de compresión, eje neutro y barras (verdes si fluyen)."""
    p = _cerrar(r.puntos)
    ax.plot(p[:, 0], p[:, 1], color=tema["principal"], linewidth=1.2)
    ax.fill(p[:, 0], p[:, 1], color=tema["actual"], alpha=0.10)
    if len(r.zona_comprimida) >= 3:
        z = _cerrar(r.zona_comprimida)
        ax.fill(z[:, 0], z[:, 1], color=tema["compresion"], alpha=0.45,
                label=f"Bloque de compresión a = {r.a * 100:.1f} cm")
    ax.axhline(r.h - r.c, color=tema["demanda"], linestyle="--", linewidth=1,
               label=f"Eje neutro c = {r.c * 100:.1f} cm")
    for capa in r.capas:
        n = capa["n_barras"]
        x0, x1 = _limites_en(r.puntos, capa["y"])
        recub = 0.12 * (x1 - x0)                          # dibujo: barras dentro del ancho
        xs = np.linspace(x0 + recub, x1 - recub, n) if n > 1 else np.array([(x0 + x1) / 2])
        ax.scatter(xs, np.full(n, capa["y"]), s=18 + capa["diametro_mm"] * 1.6,
                   color=_color_barra(capa, tema), edgecolors=tema["principal"],
                   linewidths=0.5, zorder=5)
    ax.scatter([], [], color=tema["resistencia"], label="Barra que fluye (fs = fy)")
    if not all(capa["fluye"] for capa in r.capas):
        ax.scatter([], [], color=tema["severidad"]["NARANJA"], label="Barra que no fluye")
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title(titulo)
    ax.legend(loc="center right", fontsize=7)


def _dibujar_deformaciones(ax, r, tema):
    """Diagrama lineal de deformaciones (compresión positiva, en ‰) con las barras."""
    eje_neutro = r.h - r.c
    ys = np.array([0.0, r.h])
    eps = 0.003 * (ys - eje_neutro) / r.c * 1000
    ax.plot(eps, ys, color=tema["principal"], linewidth=1.4)
    ax.fill_betweenx(ys, 0, eps, color=tema["compresion"], alpha=0.15)
    ax.axvline(0, color=tema["actual"], linewidth=0.8)
    ax.axhline(eje_neutro, color=tema["demanda"], linestyle="--", linewidth=1)
    for capa in r.capas:
        ax.plot([-capa["eps"] * 1000], [capa["y"]], "o", color=_color_barra(capa, tema), zorder=5)
    ax.axvline(-r.eps_y * 1000, color=tema["severidad"]["NARANJA"], linestyle=":",
               linewidth=1, label=f"εy = {r.eps_y * 1000:.2f} ‰")
    ax.annotate("εcu = 3 ‰", (3, r.h), textcoords="offset points", xytext=(-10, -14),
                fontsize=8, ha="right")
    ax.annotate(f"εt = {r.eps_t * 1000:.1f} ‰ → φ = {r.phi:.2f}", (-r.eps_t * 1000, 0),
                textcoords="offset points", xytext=(6, 8), fontsize=8)
    ax.set_xlabel("Deformación (‰), compresión +")
    ax.set_title("Deformaciones")
    ax.legend(loc="center right", fontsize=7)


def figura_estaciones(revision, oscuro=False):
    """Resistencia frente a demanda a lo largo de la viga: flexión arriba, cortante abajo."""
    with rc_context(TEMAS[oscuro]["rc"]):
        return _figura_estaciones(revision, TEMAS[oscuro])


def _figura_estaciones(rev, tema):
    from app.estaciones import demanda

    fig = Figure(figsize=(7.6, 6.2), dpi=110, layout="constrained")
    ax_m, ax_v = fig.subplots(2, 1, sharex=True)
    x_fino = np.linspace(0, rev.luz, 300)
    mu_fino, vu_fino = demanda(x_fino, rev.wu, rev.luz)
    for ax, demanda_fina, resistencia, demanda_est, nombre, unidad in (
        (ax_m, mu_fino, rev.phi_mn, rev.mu, "M", "kN·m"),
        (ax_v, vu_fino, rev.phi_vn, rev.vu, "V", "kN"),
    ):
        _sombrear_danos(ax, rev, tema)
        ax.plot(x_fino, demanda_fina, color=tema["demanda"], linewidth=1.6,
                label=f"Demanda {nombre}u")
        ax.plot(rev.x, resistencia, color=tema["resistencia"], linewidth=1.8,
                drawstyle="steps-mid", marker="o", markersize=3.5,
                label=f"Resistencia φ{nombre}n por estación")
        falla = demanda_est > resistencia
        if falla.any():
            ax.plot(rev.x[falla], demanda_est[falla], "X", color=tema["demanda"], markersize=9,
                    zorder=6, label="Estación que no cumple")
        ax.set_ylabel(f"{nombre} ({unidad})")
        ax.set_ylim(bottom=0)
        ax.legend(loc="best", fontsize=7)

    i = rev.indice_critico
    ax_m.set_title(f"Estación crítica x = {rev.x[i]:g} m · demanda/resistencia = "
                   f"{rev.relacion[i]:.2f}")
    ax_v.set_xlabel("Posición a lo largo de la viga x (m)")
    ax_v.set_xlim(0, rev.luz)
    return fig


def _sombrear_danos(ax, rev, tema):
    """Franja de color detrás de las estaciones con la sección dañada."""
    paso = np.min(np.diff(rev.x)) if len(rev.x) > 1 else rev.luz
    primera = True
    for e in rev.estaciones:
        if e.danada:
            ax.axvspan(max(e.x - paso / 2, 0), min(e.x + paso / 2, rev.luz),
                       color=tema["severidad"]["NARANJA"], alpha=0.12, linewidth=0,
                       label="Sección dañada" if primera else None)
            primera = False


def figura_a_png(figura):
    """Convierte una figura en bytes PNG."""
    buffer = io.BytesIO()
    figura.savefig(buffer, format="png", facecolor=figura.get_facecolor())
    return buffer.getvalue()


def guardar_figura(figura, ruta):
    figura.savefig(ruta, format="png", facecolor=figura.get_facecolor())
    return ruta
