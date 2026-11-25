"""Modelo de ingeniería: propiedades de secciones y pérdida por corrosión.

Este módulo NO depende de Flet: se puede importar y probar sin abrir la ventana.

Flujo del cálculo
-----------------
1. La geometría (vértices del polígono) la genera la librería del curso
   ``app/sections.py`` (pysections), que se usa sin modificar.
2. Las propiedades geométricas (A, centroide, Ixx, Iyy, Ixy, Zx) se calculan
   con las fórmulas de Green (fórmula del "zapatero") vectorizadas con NumPy.
   Se pueden evaluar muchas secciones a la vez (malla de evaluación).
3. Se compara la sección ideal contra la sección modificada (corroída o
   reforzada) y se clasifica la severidad por la pérdida del módulo resistente
   crítico Zx.
4. Proyección de la degradación (SciPy): suponiendo que el daño avanza de forma
   lineal desde la sección ideal hacia la modificada, ``scipy.optimize.brentq``
   encuentra el nivel de daño (y el tiempo, si se conoce la edad) en que Zx
   cruza los umbrales de 10 % y 25 % de pérdida.

Unidades: longitudes en m, áreas en m², módulos resistentes en m³, inercias en m⁴.
"""

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import brentq

from app.sections import BulbTeeGirderBridge, Deck

# ---------------------------------------------------------------------------
# Catálogo de tipos de sección y sus parámetros (nombre, descripción, unidad)
# ---------------------------------------------------------------------------
PARAMETROS = {
    "bulb_tee": [
        ("b1", "Ancho aleta superior", "m"),
        ("b2", "Ancho aleta inferior", "m"),
        ("b3", "Ancho cartela superior", "m"),
        ("b4", "Ancho cartela inferior", "m"),
        ("d1", "Altura total", "m"),
        ("d2", "Espesor aleta superior", "m"),
        ("d3", "Altura cartela superior 1", "m"),
        ("d4", "Altura cartela superior 2", "m"),
        ("d5", "Espesor aleta inferior", "m"),
        ("d6", "Altura cartela inferior 1", "m"),
        ("d7", "Altura cartela inferior 2", "m"),
        ("t1", "Espesor alma superior", "m"),
        ("t2", "Espesor alma inferior", "m"),
        ("c1", "Chaflán inferior", "m"),
    ],
    "rectangular": [
        ("width", "Ancho", "m"),
        ("thickness", "Altura / espesor", "m"),
    ],
}

NOMBRES_TIPO = {
    "bulb_tee": "Viga Bulb-Tee (puente de vigas prefabricadas)",
    "rectangular": "Sección rectangular (losa / tablero)",
}

# Caso de ejemplo: viga Bulb-Tee de 1.60 m con pérdida en la aleta inferior y el
# alma (zona típica de corrosión por escorrentía y cloruros).
EJEMPLO = {
    "tipo": "bulb_tee",
    "ideal": dict(b1=1.20, b2=0.65, b3=0.20, b4=0.20, d1=1.60, d2=0.075, d3=0.05,
                  d4=0.05, d5=0.15, d6=0.20, d7=0.05, t1=0.15, t2=0.15, c1=0.02),
    "modificada": dict(b1=1.20, b2=0.56, b3=0.20, b4=0.16, d1=1.57, d2=0.075, d3=0.05,
                       d4=0.05, d5=0.11, d6=0.20, d7=0.05, t1=0.15, t2=0.12, c1=0.02),
    "edad_anios": 25.0,
}

# Umbrales de pérdida de Zx (%) usados para la clasificación
UMBRAL_PREVENTIVO = 10.0
UMBRAL_INTERVENCION = 25.0

PROPIEDADES = [
    # clave, etiqueta, unidad
    ("area", "Área A", "m²"),
    ("xc", "Centroide Xc", "m"),
    ("yc", "Centroide Yc (desde la base)", "m"),
    ("ixx", "Inercia Ixx", "m⁴"),
    ("iyy", "Inercia Iyy", "m⁴"),
    ("ixy", "Producto de inercia Ixy", "m⁴"),
    ("zx_sup", "Módulo resistente Zx sup", "m³"),
    ("zx_inf", "Módulo resistente Zx inf", "m³"),
    ("zx_crit", "Módulo resistente crítico Zx", "m³"),
]


# ---------------------------------------------------------------------------
# Construcción de la geometría (usa pysections sin modificarla)
# ---------------------------------------------------------------------------
def validar_parametros(tipo, parametros):
    """Verifica que los parámetros existan, sean positivos y formen una sección válida.

    Lanza ``ValueError`` con un mensaje legible si algo está mal.
    """
    if tipo not in PARAMETROS:
        raise ValueError(f"Tipo de sección desconocido: {tipo}")
    p = {}
    for clave, descripcion, _ in PARAMETROS[tipo]:
        if clave not in parametros:
            raise ValueError(f"Falta el parámetro {clave} ({descripcion})")
        valor = float(parametros[clave])
        if not np.isfinite(valor) or valor <= 0:
            raise ValueError(f"{clave} ({descripcion}) debe ser mayor que cero")
        p[clave] = valor

    if tipo == "bulb_tee":
        if p["d5"] + p["d6"] + p["d7"] >= p["d1"] - (p["d2"] + p["d3"] + p["d4"]):
            raise ValueError("Las alturas d2..d7 no caben en la altura total d1")
        if p["t2"] / 2 + p["b4"] > p["b2"] / 2:
            raise ValueError("t2/2 + b4 no puede superar la mitad del ancho inferior b2")
        if p["t1"] / 2 + p["b3"] > p["b1"] / 2:
            raise ValueError("t1/2 + b3 no puede superar la mitad del ancho superior b1")
        if p["c1"] >= min(p["b2"] / 2, p["d5"]):
            raise ValueError("El chaflán c1 debe ser menor que b2/2 y que d5")
    return p


def construir_seccion(tipo, parametros):
    """Devuelve el objeto de pysections correspondiente al tipo de sección."""
    p = validar_parametros(tipo, parametros)
    if tipo == "bulb_tee":
        return BulbTeeGirderBridge(**p)
    return Deck(**p)


def altura_seccion(tipo, parametros):
    """Altura total h de la sección (m), necesaria para Zx superior."""
    return float(parametros["d1"] if tipo == "bulb_tee" else parametros["thickness"])


# ---------------------------------------------------------------------------
# Propiedades geométricas vectorizadas
# ---------------------------------------------------------------------------
def propiedades_lote(puntos, alturas):
    """Propiedades de varias secciones poligonales a la vez (vectorizado).

    Parameters
    ----------
    puntos : array (n, m, 2) o (m, 2)
        Vértices de n polígonos de m vértices (coordenadas x, y en m).
    alturas : float o array (n,)
        Altura total de cada sección (m), medida desde y = 0.

    Returns
    -------
    dict de arrays (n,) con: area, xc, yc, ixx, iyy, ixy, zx_sup, zx_inf, zx_crit.
    """
    P = np.asarray(puntos, dtype=float)
    if P.ndim == 2:
        P = P[np.newaxis, ...]
    x, y = P[..., 0], P[..., 1]
    x1, y1 = np.roll(x, -1, axis=-1), np.roll(y, -1, axis=-1)
    cruz = x * y1 - x1 * y

    area = cruz.sum(axis=-1) / 2
    signo = np.sign(area)                       # corrige el sentido de recorrido
    area = area * signo
    qx = signo * (cruz * (y + y1)).sum(axis=-1) / 6          # ∫ y dA
    qy = signo * (cruz * (x + x1)).sum(axis=-1) / 6          # ∫ x dA
    ix0 = signo * (cruz * (y**2 + y * y1 + y1**2)).sum(axis=-1) / 12
    iy0 = signo * (cruz * (x**2 + x * x1 + x1**2)).sum(axis=-1) / 12
    ixy0 = signo * (cruz * (x * y1 + 2 * x * y + 2 * x1 * y1 + x1 * y)).sum(axis=-1) / 24

    xc, yc = qy / area, qx / area
    ixx = ix0 - area * yc**2                    # teorema de ejes paralelos
    iyy = iy0 - area * xc**2
    ixy = ixy0 - area * xc * yc

    h = np.broadcast_to(np.asarray(alturas, dtype=float), area.shape)
    zx_inf = ixx / yc
    zx_sup = ixx / (h - yc)
    zx_crit = np.minimum(zx_sup, zx_inf)
    return dict(area=area, xc=xc, yc=yc, ixx=ixx, iyy=iyy, ixy=ixy,
                zx_sup=zx_sup, zx_inf=zx_inf, zx_crit=zx_crit)


def propiedades(tipo, parametros):
    """Propiedades de una sola sección como diccionario de floats."""
    seccion = construir_seccion(tipo, parametros)
    lote = propiedades_lote(seccion.points, altura_seccion(tipo, parametros))
    props = {clave: float(valor[0]) for clave, valor in lote.items()}
    if props["area"] <= 0 or props["zx_crit"] <= 0:
        raise ValueError("La geometría ingresada no forma una sección válida")
    return props


# ---------------------------------------------------------------------------
# Comparación ideal vs modificada
# ---------------------------------------------------------------------------
def variacion_porcentual(ideal, modificada):
    """((Modificada - Ideal) / Ideal) × 100. Acepta escalares o arreglos."""
    ideal = np.asarray(ideal, dtype=float)
    return (np.asarray(modificada, dtype=float) - ideal) / ideal * 100.0


def clasificar(perdida_zx):
    """Severidad según la pérdida (%) del módulo resistente crítico Zx."""
    perdida = round(float(perdida_zx), 9)
    if perdida < UMBRAL_PREVENTIVO:
        return "VERDE", "MANTENIMIENTO PREVENTIVO"
    if perdida <= UMBRAL_INTERVENCION:
        return "NARANJA", "REDISEÑO DE SU CAPACIDAD NOMINAL"
    return "ROJO", "INTERVENCIÓN INMINENTE"


@dataclass
class Proyeccion:
    """Resultado de la proyección de degradación (ver ``proyectar_degradacion``)."""
    alfa: np.ndarray                 # nivel de daño: 0 = ideal, 1 = estado inspeccionado
    capacidad_area: np.ndarray       # A(α)/A_ideal × 100
    capacidad_ixx: np.ndarray        # Ixx(α)/Ixx_ideal × 100
    capacidad_zx: np.ndarray         # Zx(α)/Zx_ideal × 100
    alfa_umbral: dict = field(default_factory=dict)   # {10.0: α*, 25.0: α*} o None
    edad_anios: float | None = None

    def tiempo_umbral(self, umbral):
        """Años desde la construcción en que se alcanza el umbral (avance lineal)."""
        a = self.alfa_umbral.get(umbral)
        if a is None or not self.edad_anios:
            return None
        return a * self.edad_anios


@dataclass
class Resultado:
    tipo: str
    ideal_param: dict
    mod_param: dict
    ideal: dict
    modificada: dict
    perdida_area: float
    perdida_ixx: float
    perdida_zx: float
    severidad: str
    dictamen: str
    proyeccion: Proyeccion
    puntos_ideal: np.ndarray
    puntos_mod: np.ndarray
    flexion: object = None           # flexion.ComparacionFlexion, si se evaluó a flexión

    @property
    def cumple(self):
        """Chequeo: la sección conserva al menos el 90 % de Zx (pérdida < 10 %)."""
        return round(self.perdida_zx, 9) < UMBRAL_PREVENTIVO

    def filas_tabla(self):
        """Filas de la tabla comparativa (para la interfaz y la memoria)."""
        filas = []
        for clave, etiqueta, unidad in PROPIEDADES:
            vi, vm = self.ideal[clave], self.modificada[clave]
            var = float(variacion_porcentual(vi, vm)) if abs(vi) > 1e-12 else 0.0
            filas.append(dict(clave=clave, propiedad=etiqueta, unidad=unidad, ideal=vi,
                              modificada=vm, diferencia=vm - vi, variacion=var))
        return filas


def _alfa_maximo(p_ideal, p_mod, tope=5.0):
    """Mayor nivel de daño α para el que todas las dimensiones siguen positivas."""
    pi = np.array(list(p_ideal.values()))
    delta = np.array([p_mod[k] for k in p_ideal]) - pi
    decrecen = delta < 0
    if not decrecen.any():
        return tope
    return float(min(tope, 0.95 * np.min(-pi[decrecen] / delta[decrecen])))


def _es_valida(tipo, parametros):
    try:
        validar_parametros(tipo, parametros)
        return True
    except ValueError:
        return False


def _parametros_en(alfa, p_ideal, p_mod):
    return {k: p_ideal[k] + alfa * (p_mod[k] - p_ideal[k]) for k in p_ideal}


def proyectar_degradacion(tipo, p_ideal, p_mod, edad_anios=None, n=200):
    """Evolución de la capacidad si el daño avanza linealmente (α = 0 → 1 → α_max).

    Como los vértices de las secciones son funciones lineales de sus cotas, la
    sección con nivel de daño α es  P(α) = P_ideal + α (P_mod − P_ideal); toda la
    malla de α se evalúa de una sola vez con ``propiedades_lote``.

    Los niveles de daño en que Zx pierde 10 % y 25 % se hallan con
    ``scipy.optimize.brentq`` sobre  f(α) = Zx(α)/Zx_ideal·100 − (100 − umbral).
    """
    alfa_max = _alfa_maximo(p_ideal, p_mod)
    # recorta α_max si la geometría deja de ser válida antes (cotas incompatibles)
    while alfa_max > 1.0 and not _es_valida(tipo, _parametros_en(alfa_max, p_ideal, p_mod)):
        alfa_max = max(1.0, alfa_max * 0.9)

    P0 = construir_seccion(tipo, p_ideal).points
    P1 = construir_seccion(tipo, p_mod).points
    alfa = np.linspace(0.0, alfa_max, n)
    h0, h1 = altura_seccion(tipo, p_ideal), altura_seccion(tipo, p_mod)
    alturas = h0 + alfa * (h1 - h0)

    if P0.shape == P1.shape:
        malla = P0[np.newaxis] + alfa[:, np.newaxis, np.newaxis] * (P1 - P0)[np.newaxis]
        lote = propiedades_lote(malla, alturas)
    else:  # caso raro: pysections eliminó un vértice repetido en una de las secciones
        secciones = [construir_seccion(tipo, _parametros_en(a, p_ideal, p_mod)).points
                     for a in alfa]
        lote = {k: np.array([propiedades_lote(s, h)[k][0] for s, h in zip(secciones, alturas)])
                for k in ("area", "ixx", "zx_crit")}

    base = propiedades_lote(P0, h0)
    cap = {k: lote[k] / base[k][0] * 100 for k in ("area", "ixx", "zx_crit")}

    def capacidad_zx(a):
        P = P0 + a * (P1 - P0) if P0.shape == P1.shape else \
            construir_seccion(tipo, _parametros_en(a, p_ideal, p_mod)).points
        return propiedades_lote(P, h0 + a * (h1 - h0))["zx_crit"][0] / base["zx_crit"][0] * 100

    alfa_umbral = {}
    for umbral in (UMBRAL_PREVENTIVO, UMBRAL_INTERVENCION):
        objetivo = 100.0 - umbral
        f = cap["zx_crit"] - objetivo
        cambios = np.nonzero(np.sign(f[:-1]) * np.sign(f[1:]) < 0)[0]
        if f[0] > 0 and len(cambios):
            i = cambios[0]
            alfa_umbral[umbral] = float(brentq(lambda a: capacidad_zx(a) - objetivo,
                                               alfa[i], alfa[i + 1], xtol=1e-10))
        else:
            alfa_umbral[umbral] = None   # el umbral no se alcanza (p. ej. reforzamiento)

    return Proyeccion(alfa, cap["area"], cap["ixx"], cap["zx_crit"], alfa_umbral,
                      float(edad_anios) if edad_anios else None)


def comparar(tipo, p_ideal, p_mod, edad_anios=None, datos_flexion=None):
    """Calcula todo el análisis ideal vs modificada y devuelve un ``Resultado``.

    Si se pasa ``datos_flexion`` (un ``flexion.DatosFlexion``), también evalúa
    la resistencia a flexión de las dos secciones y su proyección en el tiempo.
    """
    p_ideal = validar_parametros(tipo, p_ideal)
    p_mod = validar_parametros(tipo, p_mod)
    if edad_anios is not None and edad_anios <= 0:
        raise ValueError("La edad de la estructura debe ser mayor que cero")
    ideal = propiedades(tipo, p_ideal)
    mod = propiedades(tipo, p_mod)
    perdidas = -variacion_porcentual([ideal["area"], ideal["ixx"], ideal["zx_crit"]],
                                     [mod["area"], mod["ixx"], mod["zx_crit"]])
    severidad, dictamen = clasificar(perdidas[2])
    proyeccion = proyectar_degradacion(tipo, p_ideal, p_mod, edad_anios)
    resultado_flexion = None
    if datos_flexion is not None:
        from app.flexion import comparar_flexion   # import local: flexion usa este módulo
        resultado_flexion = comparar_flexion(tipo, p_ideal, p_mod, datos_flexion, edad_anios,
                                             alfa_max=float(proyeccion.alfa[-1]))
    return Resultado(
        tipo=tipo, ideal_param=p_ideal, mod_param=p_mod, ideal=ideal, modificada=mod,
        perdida_area=float(perdidas[0]), perdida_ixx=float(perdidas[1]),
        perdida_zx=float(perdidas[2]), severidad=severidad, dictamen=dictamen,
        proyeccion=proyeccion,
        puntos_ideal=construir_seccion(tipo, p_ideal).points,
        puntos_mod=construir_seccion(tipo, p_mod).points,
        flexion=resultado_flexion,
    )
