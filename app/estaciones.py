"""Revisión de la viga por estaciones: flexión y cortante a lo largo de la luz.

En campo la corrosión no es uniforme: suele ser peor cerca de juntas, drenajes
o apoyos. Este módulo revisa la viga en varias estaciones x (por ejemplo, cada
metro) con el daño medido en cada una, y compara resistencia contra demanda:

* Flexión:  Mu(x) = wu·x·(L − x)/2      frente a  φMn con el acero de esa estación
* Cortante: Vu(x) = wu·|L/2 − x|        frente a  φVn = 0.75·(Vc + Vs)   (NSR-10 C.11)
      Vc = 0.17·√f'c·bw·d                  (C.11.2.1.1, concreto de peso normal)
      Vs = Av·fyt·d / s ≤ 0.66·√f'c·bw·d   (C.11.4.7.2 y C.11.4.7.9)

Mu, Vu y φVn se calculan con arreglos de NumPy para todas las estaciones a la
vez. φMn exige resolver el equilibrio de la sección (scipy brentq, en
``flexion.evaluar_flexion``), así que se calcula una vez por cada combinación
distinta de sección y pérdida de acero y se reutiliza.

Supuestos: viga simplemente apoyada con carga uniforme; wu se calcula con el peso
propio de la sección de diseño en toda la luz; las cotas de una estación dañada
son las de la sección inspeccionada.

Unidades: m, mm (diámetros), MPa, kN, kN/m y kN·m.
"""

import math
from dataclasses import asdict, dataclass

import numpy as np

from app import flexion, modelo

PHI_CORTANTE = 0.75          # NSR-10 C.9.3.2.3


@dataclass
class Estribos:
    """Refuerzo transversal: estribos de ``ramas`` ramas separados ``separacion`` m."""
    diametro_mm: float
    ramas: int
    separacion: float            # m
    fyt: float = 420.0           # MPa

    @property
    def area_mm2(self):
        """Av: área de todas las ramas de un estribo (mm²)."""
        return self.ramas * math.pi * self.diametro_mm**2 / 4


@dataclass
class Estacion:
    """Punto de revisión a ``x`` m del apoyo izquierdo, con el daño medido ahí."""
    x: float
    danada: bool = False             # True: usa las cotas de la sección inspeccionada
    perdida_acero: float = 0.0       # %, acero longitudinal
    perdida_estribos: float = 0.0    # %, estribos


# Estribos No. 3 de dos ramas cada 20 cm, coherentes con flexion.EJEMPLO
EJEMPLO_ESTRIBOS = Estribos(diametro_mm=9.5, ramas=2, separacion=0.20, fyt=420.0)


def generar_estaciones(luz, paso=1.0):
    """Estaciones sanas cada ``paso`` m, de 0 a L (incluye el apoyo derecho)."""
    if luz <= 0 or paso <= 0:
        raise ValueError("La luz y el paso deben ser mayores que cero")
    xs = np.arange(0.0, luz + 1e-9, paso)
    if luz - xs[-1] > 1e-9:
        xs = np.append(xs, luz)
    return [Estacion(x=round(float(x), 3)) for x in xs]


def ejemplo_estaciones(luz=17.0):
    """Daño típico de una inspección: junta con filtración entre 1 y 4 m (estribos y
    acero muy corroídos), zona central dañada y el resto con corrosión leve."""
    estaciones = generar_estaciones(luz, 1.0)
    for e in estaciones:
        if 1.0 <= e.x <= 4.0:
            e.danada, e.perdida_acero, e.perdida_estribos = True, 35.0, 45.0
        elif 7.0 <= e.x <= 10.0:
            e.danada, e.perdida_acero, e.perdida_estribos = True, 20.0, 10.0
        else:
            e.perdida_acero = 5.0
    return estaciones


# ---------------------------------------------------------------------------
# Demanda y resistencia a cortante (vectorizadas)
# ---------------------------------------------------------------------------
def demanda(x, wu, luz):
    """Mu(x) (kN·m) y Vu(x) (kN) de una viga simplemente apoyada con carga uniforme wu."""
    x = np.asarray(x, dtype=float)
    return wu * x * (luz - x) / 2, wu * np.abs(luz / 2 - x)


def resistencia_cortante(fc, bw, d, estribos, factor_estribos=1.0):
    """φVn (kN), Vc (kN) y Vs (kN). ``bw``, ``d`` y ``factor_estribos`` pueden ser arreglos."""
    bw, d = np.asarray(bw, dtype=float), np.asarray(d, dtype=float)
    raiz = math.sqrt(fc)
    vc = 0.17 * raiz * bw * d                                         # MN
    av = estribos.area_mm2 * 1e-6 * np.asarray(factor_estribos, dtype=float)   # m²
    vs = np.minimum(av * estribos.fyt * d / estribos.separacion, 0.66 * raiz * bw * d)
    return PHI_CORTANTE * (vc + vs) * 1000, vc * 1000, vs * 1000


# ---------------------------------------------------------------------------
# Revisión completa
# ---------------------------------------------------------------------------
@dataclass
class ResultadoEstaciones:
    estaciones: list
    estribos: Estribos
    luz: float
    wu: float                    # kN/m
    x: np.ndarray                # m
    mu: np.ndarray               # kN·m
    phi_mn: np.ndarray           # kN·m
    vu: np.ndarray               # kN
    phi_vn: np.ndarray           # kN
    vc: np.ndarray               # kN
    vs: np.ndarray               # kN

    @property
    def relacion_m(self):
        return self.mu / self.phi_mn

    @property
    def relacion_v(self):
        return self.vu / self.phi_vn

    @property
    def relacion(self):
        """Peor relación demanda / resistencia de cada estación."""
        return np.maximum(self.relacion_m, self.relacion_v)

    @property
    def cumple(self):
        return self.relacion <= 1.0

    @property
    def indice_critico(self):
        return int(np.argmax(self.relacion))

    @property
    def cumple_todo(self):
        return bool(self.cumple.all())

    def resumen(self):
        """Frase con la estación crítica (la usan la interfaz y la memoria)."""
        i = self.indice_critico
        causa = "cortante" if self.relacion_v[i] >= self.relacion_m[i] else "flexión"
        fallan = int((~self.cumple).sum())
        if fallan == 0:
            estado = "todas las estaciones cumplen"
        else:
            estado = f"{fallan} de {len(self.x)} estaciones no {'cumple' if fallan == 1 else 'cumplen'}"
        return (f"Estación crítica: x = {self.x[i]:g} m, controla {causa} "
                f"(demanda / resistencia = {self.relacion[i]:.2f}); {estado}.")

    def filas(self):
        """Una fila por estación con todos los resultados (para tablas)."""
        return [dict(x=e.x, danada=e.danada, perdida_acero=e.perdida_acero,
                     perdida_estribos=e.perdida_estribos, mu=float(self.mu[k]),
                     phi_mn=float(self.phi_mn[k]), vu=float(self.vu[k]),
                     phi_vn=float(self.phi_vn[k]), relacion=float(self.relacion[k]),
                     cumple=bool(self.cumple[k]))
                for k, e in enumerate(self.estaciones)]


def validar_estaciones(estaciones, estribos, luz):
    if not estaciones:
        raise ValueError("Agregue al menos una estación")
    if estribos.diametro_mm <= 0 or estribos.ramas < 1 or estribos.separacion <= 0 \
            or estribos.fyt <= 0:
        raise ValueError("Los estribos deben tener diámetro, ramas, separación y fyt positivos")
    for i, e in enumerate(estaciones, start=1):
        if not 0 <= e.x <= luz:
            raise ValueError(f"Estación {i}: x = {e.x:g} m está fuera de la viga (0 a {luz:g} m)")
        if not (0 <= e.perdida_acero < 100 and 0 <= e.perdida_estribos < 100):
            raise ValueError(f"Estación {i}: las pérdidas deben estar entre 0 % y 100 %")


def _resistencia_seccion(tipo, p_ideal, p_mod, datos, cache, estacion):
    """φMn, d y bw de la sección de una estación (cada combinación se calcula una vez)."""
    clave = (estacion.danada, estacion.perdida_acero)
    if clave not in cache:
        params = p_mod if estacion.danada else p_ideal
        r = flexion.evaluar_flexion(tipo, params, datos, 1 - estacion.perdida_acero / 100)
        cache[clave] = (r.phi_mn, r.d_efectivo, flexion.ancho_alma(tipo, params))
    return cache[clave]


def evaluar_estaciones(tipo, p_ideal, p_mod, datos, estribos, estaciones):
    """Revisa flexión y cortante en todas las estaciones y devuelve un ResultadoEstaciones."""
    validar_estaciones(estaciones, estribos, datos.luz)
    estaciones = sorted(estaciones, key=lambda e: e.x)
    area = modelo.propiedades(tipo, p_ideal)["area"]
    wu, _ = flexion.momento_ultimo(datos.luz, flexion.GAMMA_CONCRETO * area + datos.carga_muerta,
                                   datos.carga_viva)

    cache = {}
    secciones = np.array([_resistencia_seccion(tipo, p_ideal, p_mod, datos, cache, e)
                          for e in estaciones])              # columnas: φMn, d, bw
    x = np.array([e.x for e in estaciones])
    mu, vu = demanda(x, wu, datos.luz)
    factor = 1 - np.array([e.perdida_estribos for e in estaciones]) / 100
    phi_vn, vc, vs = resistencia_cortante(datos.fc, secciones[:, 2], secciones[:, 1],
                                          estribos, factor)
    return ResultadoEstaciones(estaciones=estaciones, estribos=estribos, luz=datos.luz,
                               wu=float(wu), x=x, mu=mu, phi_mn=secciones[:, 0], vu=vu,
                               phi_vn=phi_vn, vc=vc, vs=vs)


# ---------------------------------------------------------------------------
# Conversión para la base de datos
# ---------------------------------------------------------------------------
def estribos_a_diccionario(estribos):
    return asdict(estribos)


def estribos_desde_diccionario(datos):
    return Estribos(float(datos["diametro_mm"]), int(datos["ramas"]),
                    float(datos["separacion"]), float(datos["fyt"]))


def estaciones_desde_filas(filas):
    return [Estacion(float(f["x"]), bool(f["danada"]), float(f["perdida_acero"]),
                     float(f["perdida_estribos"])) for f in filas]
