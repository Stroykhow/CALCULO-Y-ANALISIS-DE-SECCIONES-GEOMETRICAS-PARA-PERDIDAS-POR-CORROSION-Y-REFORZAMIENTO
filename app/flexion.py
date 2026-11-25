"""Análisis a flexión de vigas de concreto reforzado (NSR-10 / ACI 318).

Este módulo NO depende de Flet. Usa la geometría real de la sección (el polígono
de ``sections.py``) para calcular la resistencia a flexión con el bloque
rectangular equivalente de Whitney y compatibilidad de deformaciones.

Flujo del cálculo
-----------------
1. Demanda: viga simplemente apoyada de luz L con carga muerta (peso propio +
   carga adicional) y carga viva distribuidas →  wu = máx(1.2D + 1.6L, 1.4D)
   y  Mu = wu·L²/8  (NSR-10 B.2.4).
2. Resistencia: se busca la profundidad del eje neutro c que equilibra
   C = T. La zona comprimida es el polígono recortado por encima de h − a,
   con a = β1·c, así que sirve para la Bulb-Tee y para la losa.
   La ecuación C(c) − T(c) = 0 se resuelve con ``scipy.optimize.brentq``.
3. Mn = momento del par interno;  φ según εt (NSR-10 C.9.3.2);  φMn ≥ Mu.
4. Corrosión del acero: la sección modificada usa el área de las barras
   reducida en el porcentaje de pérdida indicado.
5. Proyección: si el daño (concreto y acero) avanza linealmente, brentq halla
   el nivel de daño, y el año, en que φMn deja de cubrir Mu.

Unidades: m, mm (diámetros), MPa, kN, kN/m y kN·m.
"""

import math
from dataclasses import asdict, dataclass, field

import numpy as np
from scipy.optimize import brentq

from app import modelo

ES = 200_000.0          # MPa, módulo de elasticidad del acero
EPS_CU = 0.003          # deformación última del concreto
GAMMA_CONCRETO = 24.0   # kN/m³, peso unitario del concreto reforzado
EPS_T_MIN = 0.004       # NSR-10 C.10.3.5: εt mínimo en elementos a flexión

# Diámetros nominales de barras corrugadas (NSR-10 C.3.5.3), en mm
BARRAS = {"No. 3": 9.5, "No. 4": 12.7, "No. 5": 15.9, "No. 6": 19.1,
          "No. 7": 22.2, "No. 8": 25.4, "No. 9": 28.7, "No. 10": 32.3}


@dataclass
class Capa:
    """Una fila de barras a la misma altura."""
    n_barras: int
    diametro_mm: float
    y: float                # m, altura del centro de las barras medida desde la base

    @property
    def area_mm2(self):
        return self.n_barras * math.pi * self.diametro_mm**2 / 4


@dataclass
class DatosFlexion:
    """Materiales, refuerzo y cargas de la viga."""
    fc: float                       # MPa, resistencia del concreto
    fy: float                       # MPa, fluencia del acero
    capas: list                     # lista de Capa
    luz: float                      # m, luz de la viga simplemente apoyada
    carga_muerta: float = 0.0       # kN/m, adicional al peso propio (losa, asfalto…)
    carga_viva: float = 0.0         # kN/m
    perdida_acero: float = 0.0      # %, pérdida de área de las barras por corrosión

    def a_diccionario(self):
        """Datos sin las capas, para guardar como JSON."""
        datos = asdict(self)
        datos.pop("capas")
        return datos

    @classmethod
    def desde_diccionario(cls, datos, capas):
        capas = [c if isinstance(c, Capa) else Capa(int(c["n_barras"]), float(c["diametro_mm"]),
                                                    float(c["y"])) for c in capas]
        return cls(capas=capas, **{k: float(v) for k, v in datos.items()})


# Ejemplo coherente con modelo.EJEMPLO: viga Bulb-Tee de 17 m con dos capas de
# barras No. 8 en la aleta inferior y 20 % de pérdida de acero por corrosión.
EJEMPLO = DatosFlexion(
    fc=35.0, fy=420.0,
    capas=[Capa(5, 25.4, 0.06), Capa(5, 25.4, 0.12)],
    luz=17.0, carga_muerta=12.0, carga_viva=18.0, perdida_acero=20.0,
)


# ---------------------------------------------------------------------------
# Coeficientes de la NSR-10
# ---------------------------------------------------------------------------
def beta1(fc):
    """β1 del bloque de Whitney (NSR-10 C.10.2.7.3)."""
    if fc <= 28:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc - 28) / 7)


def factor_phi(eps_t, eps_y):
    """φ según la deformación del acero extremo en tensión (NSR-10 C.9.3.2)."""
    if eps_t >= 0.005:
        return 0.90
    if eps_t <= eps_y:
        return 0.65
    return 0.65 + 0.25 * (eps_t - eps_y) / (0.005 - eps_y)


def momento_ultimo(luz, carga_muerta_total, carga_viva):
    """wu (kN/m) y Mu (kN·m) de una viga simplemente apoyada."""
    wu = max(1.2 * carga_muerta_total + 1.6 * carga_viva, 1.4 * carga_muerta_total)
    return wu, wu * luz**2 / 8


# ---------------------------------------------------------------------------
# Geometría de la zona comprimida
# ---------------------------------------------------------------------------
def recortar_arriba(puntos, y0):
    """Parte del polígono que queda por encima de la recta y = y0 (Sutherland–Hodgman).

    Vectorizado: por cada lado A→B se conserva A si está arriba y se agrega el punto
    de corte si el lado cruza la recta. Las dos candidatas de cada lado se apilan en
    un arreglo (n, 2, 2) y una máscara booleana elige cuáles quedan, en orden.
    """
    A = np.asarray(puntos, dtype=float)
    B = np.roll(A, -1, axis=0)
    a_dentro, b_dentro = A[:, 1] >= y0, B[:, 1] >= y0
    cruza = a_dentro != b_dentro
    dy = B[:, 1] - A[:, 1]
    t = np.divide(y0 - A[:, 1], dy, out=np.zeros_like(dy), where=dy != 0)
    corte = A + t[:, np.newaxis] * (B - A)
    candidatos = np.stack([A, corte], axis=1)            # (n, 2, 2)
    mascara = np.stack([a_dentro, cruza], axis=1)        # (n, 2)
    return candidatos[mascara].reshape(-1, 2)


def _zona_comprimida(puntos, h, a):
    """Área (m²), centroide yc (m) y vértices de la zona comprimida de altura a."""
    zona = recortar_arriba(puntos, h - a)
    if len(zona) < 3:
        return 0.0, h, zona
    props = modelo.propiedades_lote(zona, h)
    return float(props["area"][0]), float(props["yc"][0]), zona


# ---------------------------------------------------------------------------
# Resistencia a flexión de una sección
# ---------------------------------------------------------------------------
@dataclass
class ResultadoFlexion:
    fc: float
    fy: float
    beta1: float
    c: float                    # m, profundidad del eje neutro desde la fibra superior
    a: float                    # m, altura del bloque de Whitney
    compresion_kN: float        # fuerza en el concreto comprimido
    capas: list                 # dicts por capa: As, d, εs, fs, fluye
    as_total_mm2: float
    d_efectivo: float           # m, centroide del acero medido desde arriba
    eps_t: float
    eps_y: float
    phi: float
    mn: float                   # kN·m
    phi_mn: float               # kN·m
    mcr: float                  # kN·m, momento de agrietamiento
    peso_propio: float          # kN/m
    wu: float                   # kN/m
    mu: float                   # kN·m
    relacion: float             # Mu / φMn
    cumple: bool                # φMn ≥ Mu
    ductil: bool                # εt ≥ 0.004
    as_min_mm2: float
    cumple_as_min: bool
    h: float
    puntos: np.ndarray = field(repr=False, default=None)
    zona_comprimida: np.ndarray = field(repr=False, default=None)


def validar_datos(datos, h):
    """Revisa materiales, refuerzo y cargas. Lanza ValueError con un mensaje claro."""
    if datos.fc <= 0 or datos.fy <= 0:
        raise ValueError("f'c y fy deben ser mayores que cero")
    if datos.luz <= 0:
        raise ValueError("La luz de la viga debe ser mayor que cero")
    if datos.carga_muerta < 0 or datos.carga_viva < 0:
        raise ValueError("Las cargas no pueden ser negativas")
    if not 0 <= datos.perdida_acero < 100:
        raise ValueError("La pérdida de acero debe estar entre 0 % y 100 %")
    if not datos.capas:
        raise ValueError("Agregue al menos una capa de barras")
    for i, capa in enumerate(datos.capas, start=1):
        if capa.n_barras < 1 or capa.diametro_mm <= 0:
            raise ValueError(f"Capa {i}: el número de barras y el diámetro deben ser positivos")
        if not 0 < capa.y < h:
            raise ValueError(f"Capa {i}: la altura y = {capa.y:g} m está fuera de la sección "
                             f"(0 < y < {h:g} m)")


def _fuerzas_internas(c, puntos, h, acero, fc, fy):
    """Fuerzas para un eje neutro a profundidad c (m). Fuerzas en MN, esfuerzos en MPa.

    ``acero`` = (As en m², y de cada capa en m). Tensión positiva, compresión negativa.
    """
    As, y_barras = acero
    d = h - y_barras
    a = min(beta1(fc) * c, h)
    area_c, yc_c, zona = _zona_comprimida(puntos, h, a)
    eps = EPS_CU * (d - c) / c
    fs = np.clip(ES * eps, -fy, fy)
    # las barras dentro del bloque desplazan concreto comprimido: se descuenta 0.85·f'c·As
    tension = As * fs + np.where(y_barras >= h - a, 0.85 * fc * As, 0.0)
    return dict(a=a, compresion=0.85 * fc * area_c, yc_c=yc_c, zona=zona,
                eps=eps, fs=fs, tension=tension)


def _resolver_eje_neutro(puntos, h, acero, fc, fy):
    """Profundidad c del eje neutro que cumple C − ΣT = 0 (scipy.optimize.brentq).

    C − ΣT crece con c (más concreto comprimido y menos deformación del acero), así que
    entre c ≈ 0 y c = h/β1 (bloque en toda la altura) hay una sola raíz.
    """
    def desequilibrio(c):
        f = _fuerzas_internas(c, puntos, h, acero, fc, fy)
        return f["compresion"] - f["tension"].sum()

    c_min, c_max = 1e-6 * h, h / beta1(fc)
    if desequilibrio(c_max) <= 0:
        raise ValueError("El acero es excesivo: ni toda la sección comprimida equilibra la tensión")
    if desequilibrio(c_min) >= 0:
        raise ValueError("No hay acero en tensión: coloque barras en la parte inferior")
    return brentq(desequilibrio, c_min, c_max, xtol=1e-12)


def _demanda(area, datos):
    """Peso propio (kN/m), wu (kN/m) y Mu (kN·m) de la viga simplemente apoyada."""
    peso = GAMMA_CONCRETO * area
    wu, mu = momento_ultimo(datos.luz, peso + datos.carga_muerta, datos.carga_viva)
    return peso, wu, mu


def _acero_minimo(tipo, p, fc, fy, d_efectivo):
    """As,mín (m²) = máx(0.25·√f'c, 1.4)/fy · bw · d   (NSR-10 C.10.5.1)."""
    bw = p["width"] if tipo == "rectangular" else min(p["t1"], p["t2"])
    return max(0.25 * math.sqrt(fc), 1.4) / fy * bw * d_efectivo


def evaluar_flexion(tipo, parametros, datos, factor_acero=1.0):
    """Resistencia a flexión y chequeo φMn ≥ Mu de una sección.

    ``factor_acero`` multiplica el área de todas las barras (1 = acero sano).
    """
    p = modelo.validar_parametros(tipo, parametros)
    puntos = modelo.construir_seccion(tipo, p).points
    h = modelo.altura_seccion(tipo, p)
    geo = modelo.propiedades(tipo, p)
    validar_datos(datos, h)

    fc, fy = datos.fc, datos.fy
    As = np.array([cp.area_mm2 for cp in datos.capas]) * 1e-6 * factor_acero    # m²
    y_barras = np.array([cp.y for cp in datos.capas])
    d = h - y_barras                                                        # m, desde arriba
    acero = (As, y_barras)

    c = _resolver_eje_neutro(puntos, h, acero, fc, fy)
    f = _fuerzas_internas(c, puntos, h, acero, fc, fy)
    mn = (f["compresion"] * f["yc_c"] - (f["tension"] * y_barras).sum()) * 1000   # kN·m
    eps_t = float(f["eps"][np.argmax(d)])
    phi = factor_phi(eps_t, fy / ES)
    peso, wu, mu = _demanda(geo["area"], datos)
    d_ef = float((As * d).sum() / As.sum())
    as_min = _acero_minimo(tipo, p, fc, fy, d_ef)

    capas = [dict(n_barras=cp.n_barras, diametro_mm=cp.diametro_mm, y=cp.y, d=float(di),
                  as_mm2=float(ai * 1e6), eps=float(ei), fs=float(fi), fluye=abs(fi) >= fy - 1e-9)
             for cp, di, ai, ei, fi in zip(datos.capas, d, As, f["eps"], f["fs"])]

    return ResultadoFlexion(
        fc=fc, fy=fy, beta1=beta1(fc), c=float(c), a=float(f["a"]),
        compresion_kN=float(f["compresion"] * 1000), capas=capas,
        as_total_mm2=float(As.sum() * 1e6), d_efectivo=d_ef, eps_t=eps_t, eps_y=fy / ES,
        phi=phi, mn=float(mn), phi_mn=float(phi * mn),
        mcr=0.62 * math.sqrt(fc) * geo["ixx"] / geo["yc"] * 1000,           # kN·m
        peso_propio=float(peso), wu=float(wu), mu=float(mu), relacion=float(mu / (phi * mn)),
        cumple=bool(phi * mn >= mu), ductil=eps_t >= EPS_T_MIN, as_min_mm2=as_min * 1e6,
        cumple_as_min=bool(As.sum() >= as_min), h=h, puntos=puntos, zona_comprimida=f["zona"],
    )


# ---------------------------------------------------------------------------
# Comparación ideal vs modificada y proyección en el tiempo
# ---------------------------------------------------------------------------
@dataclass
class ComparacionFlexion:
    datos: DatosFlexion
    ideal: ResultadoFlexion
    modificada: ResultadoFlexion
    perdida_phi_mn: float               # %
    alfa: np.ndarray                    # nivel de daño
    phi_mn_pct: np.ndarray              # φMn(α) / φMn_ideal × 100
    mu_pct: np.ndarray                  # Mu(α) / φMn_ideal × 100
    alfa_falla: float | None            # α en que φMn = Mu
    edad_anios: float | None = None

    @property
    def tiempo_falla(self):
        """Años desde la construcción en que φMn deja de cubrir Mu (avance lineal)."""
        if self.alfa_falla is None or not self.edad_anios:
            return None
        return self.alfa_falla * self.edad_anios

    def texto_vida(self):
        """Frase sobre cuándo deja de cumplir (la usan la interfaz y la memoria)."""
        if self.alfa_falla == 0.0:
            return "No cumple a flexión ni con la sección de diseño."
        if self.tiempo_falla is not None:
            restante = self.tiempo_falla - self.edad_anios
            cuando = "hace" if restante < 0 else "dentro de"
            return (f"Si el daño avanza al mismo ritmo, φMn deja de cubrir Mu a los "
                    f"{self.tiempo_falla:.1f} años ({cuando} {abs(restante):.1f} años).")
        if self.alfa_falla is not None:
            return f"φMn deja de cubrir Mu con un nivel de daño α = {self.alfa_falla:.2f}."
        return "φMn sigue cubriendo Mu en todo el rango de daño proyectado."


def _margen(alfa, tipo, p_ideal, p_mod, datos):
    """(φMn − Mu, φMn, Mu) en kN·m con el concreto y el acero degradados al nivel α."""
    params = {k: p_ideal[k] + alfa * (p_mod[k] - p_ideal[k]) for k in p_ideal}
    factor = max(1.0 - alfa * datos.perdida_acero / 100, 0.01)
    r = evaluar_flexion(tipo, params, datos, factor)
    return r.phi_mn - r.mu, r.phi_mn, r.mu


def _proyectar_flexion(tipo, p_ideal, p_mod, datos, alfa_max, n):
    """Curvas φMn(α) y Mu(α) y el nivel de daño α en que φMn = Mu.

    Cada α exige su propio equilibrio no lineal (un brentq interno), por eso la malla
    se recorre punto a punto; los resultados se guardan en arreglos de NumPy.
    """
    alfa = np.linspace(0.0, alfa_max, n)
    filas = np.full((n, 3), np.nan)
    for i, a in enumerate(alfa):
        try:
            filas[i] = _margen(a, tipo, p_ideal, p_mod, datos)
        except ValueError:                       # geometría o acero fuera de rango
            pass

    f, validos = filas[:, 0], ~np.isnan(filas[:, 0])
    alfa_falla = None
    if validos[0] and f[0] <= 0:
        alfa_falla = 0.0                         # ya no cumple con la sección de diseño
    elif validos[0]:
        cruces = np.nonzero((f[:-1] > 0) & (f[1:] <= 0) & validos[:-1] & validos[1:])[0]
        if len(cruces):
            i = cruces[0]
            alfa_falla = float(brentq(lambda a: _margen(a, tipo, p_ideal, p_mod, datos)[0],
                                      alfa[i], alfa[i + 1], xtol=1e-8))
    return alfa, filas[:, 1], filas[:, 2], alfa_falla


def comparar_flexion(tipo, p_ideal, p_mod, datos, edad_anios=None, alfa_max=3.0, n=60):
    """Flexión de la sección ideal (acero sano) y de la modificada (acero corroído)."""
    ideal = evaluar_flexion(tipo, p_ideal, datos, 1.0)
    mod = evaluar_flexion(tipo, p_mod, datos, 1.0 - datos.perdida_acero / 100)
    alfa, phi_mn, mu, alfa_falla = _proyectar_flexion(tipo, p_ideal, p_mod, datos, alfa_max, n)
    return ComparacionFlexion(
        datos=datos, ideal=ideal, modificada=mod,
        perdida_phi_mn=float((ideal.phi_mn - mod.phi_mn) / ideal.phi_mn * 100),
        alfa=alfa, phi_mn_pct=phi_mn / ideal.phi_mn * 100, mu_pct=mu / ideal.phi_mn * 100,
        alfa_falla=alfa_falla, edad_anios=float(edad_anios) if edad_anios else None,
    )
