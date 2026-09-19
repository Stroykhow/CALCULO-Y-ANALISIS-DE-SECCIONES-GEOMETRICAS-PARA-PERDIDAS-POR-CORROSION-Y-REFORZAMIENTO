"""Comparison of ideal and modified cross-sections.

The existing section classes remain the source of all geometric properties.
This module only adapts their public properties to a common comparison model.
"""

from dataclasses import dataclass
from math import isfinite

import matplotlib.pyplot as plt
import numpy as np


@dataclass(frozen=True)
class SectionProperties:
    area: float
    xc: float
    yc: float
    ixx: float
    iyy: float
    ixy: float
    zx_sup: float
    zx_inf: float
    zx_critical: float


@dataclass(frozen=True)
class ComparisonValue:
    ideal: float
    modified: float
    difference: float
    variation_percent: float
    capacity_percent: float


def _value(section, name, fallback=None):
    value = getattr(section, name, fallback)
    if callable(value):
        value = value()
    if value is None:
        raise ValueError("La sección no proporciona la propiedad '{}'".format(name))
    value = float(value)
    if not isfinite(value):
        raise ValueError("La propiedad '{}' debe ser finita".format(name))
    return value


_MISSING = object()


def _first_value(section, names, default=_MISSING):
    for name in names:
        if hasattr(section, name):
            return _value(section, name)
    if default is not _MISSING:
        if default is None:
            return None
        return float(default)
    raise ValueError("La sección no proporciona ninguna de estas propiedades: {}".format(
        ", ".join(names)
    ))


def extract_properties(section):
    """Extract properties without changing the existing calculation engine."""
    area = _value(section, "area")
    xc = _first_value(section, ("x", "y"), 0.0)
    yc = _first_value(section, ("z", "zi"), 0.0)

    # The original polygon engine calls its horizontal-axis inertia Iyy.
    ixx = _first_value(section, ("Ixx", "Iyy"))
    iyy = _first_value(section, ("Iyy_vertical", "Izz"), 0.0)
    ixy = _first_value(section, ("Ixy",), 0.0)

    zx_sup = _first_value(section, ("Zx_sup", "ws"), None)
    zx_inf = _first_value(section, ("Zx_inf", "wi"), None)
    if zx_sup is None or zx_inf is None:
        height = _first_value(section, ("height",), None)
        if height is None or yc <= 0 or height <= yc:
            raise ValueError("No se pueden calcular los módulos resistentes Zx")
        zx_inf = ixx / yc
        zx_sup = ixx / (height - yc)
    zx_critical = min(abs(zx_sup), abs(zx_inf))

    properties = SectionProperties(
        area, xc, yc, ixx, iyy, ixy, zx_sup, zx_inf, zx_critical
    )
    _validate_properties(properties)
    return properties


def _validate_properties(properties):
    if properties.area <= 0:
        raise ValueError("El área debe ser mayor que cero")
    for name in ("ixx", "iyy", "zx_sup", "zx_inf", "zx_critical"):
        if getattr(properties, name) < 0:
            raise ValueError("La propiedad '{}' no puede ser negativa".format(name))
    if properties.zx_critical <= 0:
        raise ValueError("El módulo resistente crítico debe ser mayor que cero")


def percentage_variation(ideal, modified):
    """Return ((modified - ideal) / ideal) * 100."""
    ideal = float(ideal)
    modified = float(modified)
    if not isfinite(ideal) or not isfinite(modified):
        raise ValueError("La comparación requiere valores finitos")
    if abs(ideal) < 1e-12:
        if abs(modified) < 1e-12:
            return 0.0
        return float("inf")
    return (modified - ideal) / ideal * 100.0


def relative_capacity(ideal, modified):
    ideal = float(ideal)
    modified = float(modified)
    if not isfinite(ideal) or not isfinite(modified):
        raise ValueError("La capacidad relativa requiere valores finitos")
    if abs(ideal) < 1e-12:
        if abs(modified) < 1e-12:
            return 100.0
        return float("inf")
    return modified / ideal * 100.0


class SectionComparison:
    """Compare an ideal section against a modified section."""

    def __init__(self, ideal, modified):
        self.ideal_section = ideal
        self.modified_section = modified
        self.ideal = extract_properties(ideal)
        self.modified = extract_properties(modified)
        self.severity, self.recommendation = self._classify()

    def _value(self, name):
        ideal = getattr(self.ideal, name)
        modified = getattr(self.modified, name)
        return ComparisonValue(
            ideal,
            modified,
            modified - ideal,
            percentage_variation(ideal, modified),
            relative_capacity(ideal, modified),
        )

    @property
    def values(self):
        names = (
            ("area", "Área"),
            ("xc", "Xc"),
            ("yc", "Yc"),
            ("ixx", "Ixx"),
            ("iyy", "Iyy"),
            ("ixy", "Ixy"),
            ("zx_sup", "Zx Sup"),
            ("zx_inf", "Zx Inf"),
            ("zx_critical", "Zx Crítico"),
        )
        return [(label, self._value(name)) for name, label in names]

    def _classify(self):
        loss = round(
            -percentage_variation(self.ideal.zx_critical, self.modified.zx_critical),
            12,
        )
        if loss < 10:
            return "VERDE", "MANTENIMIENTO PREVENTIVO"
        if loss <= 25:
            return "NARANJA", "REDISEÑO DE SU CAPACIDAD NOMINAL"
        return "ROJO", "INTERVENCIÓN INMINENTE"

    def table_rows(self):
        return [
            {
                "Propiedad": label,
                "Ideal": value.ideal,
                "Modificada": value.modified,
                "Diferencia": value.difference,
                "Variación (%)": value.variation_percent,
            }
            for label, value in self.values
        ]

    def plot(self, filename=None):
        colors = {"VERDE": "green", "NARANJA": "orange", "ROJO": "red"}
        severity_color = colors[self.severity]
        figure, axes = plt.subplots(1, 3, figsize=(18, 6), constrained_layout=True)
        self._plot_geometry(axes[0], self.ideal_section, "SECCIÓN IDEAL", "tab:blue", -0.5)
        self._plot_geometry(
            axes[0], self.modified_section, "SECCIÓN MODIFICADA", severity_color, 0.5
        )
        self._plot_performance(axes[1])
        self._plot_verdict(axes[2], severity_color)
        if filename:
            figure.savefig(filename, bbox_inches="tight")
        return figure, axes

    @staticmethod
    def _plot_geometry(axis, section, label, color, offset):
        points = getattr(section, "points", None)
        if points is None:
            raise ValueError("La sección debe exponer puntos para graficar su geometría")
        points = np.asarray(points, dtype=float)
        shifted = points.copy()
        shifted[:, 0] += offset * (np.ptp(points[:, 0]) + 1.0)
        closed = np.vstack((shifted, shifted[0]))
        axis.plot(closed[:, 0], closed[:, 1], color=color, label=label)
        axis.fill(closed[:, 0], closed[:, 1], color=color, alpha=0.18)
        yc = float(getattr(section, "z", getattr(section, "zi", 0.0)))
        axis.scatter([offset * (np.ptp(points[:, 0]) + 1.0)], [yc], color=color, zorder=3)
        axis.axhline(yc, color=color, linestyle="--", linewidth=0.8)
        axis.axvline(0, color="black", linewidth=0.6)
        axis.set_title("GEOMETRÍA")
        axis.set_aspect("equal", adjustable="datalim")
        axis.grid(True)
        axis.legend()

    def _plot_performance(self, axis):
        labels = ["Área", "Ixx", "Zx"]
        values = [self._value("area"), self._value("ixx"), self._value("zx_critical")]
        relative = [value.capacity_percent for value in values]
        positions = np.arange(len(labels))
        axis.barh(positions, [100] * len(labels), color="tab:blue", alpha=0.35, label="Ideal")
        axis.barh(positions, relative, color="tab:orange", label="Modificada")
        for position, capacity in zip(positions, relative):
            axis.text(capacity + 1, position, "{:.2f}% ({:+.2f}%)".format(
                capacity, capacity - 100
            ), va="center")
        axis.set_yticks(positions, labels)
        axis.set_xlabel("Capacidad relativa (%)")
        axis.set_title("DESEMPEÑO")
        axis.set_xlim(left=0)
        axis.legend()

    def _plot_verdict(self, axis, severity_color):
        area_loss = -self._value("area").variation_percent
        inertia_loss = -self._value("ixx").variation_percent
        zx_loss = -self._value("zx_critical").variation_percent
        text = (
            "DICTAMEN TÉCNICO\n\n"
            "Pérdida de área: {:.2f}%\n"
            "Pérdida de inercia: {:.2f}%\n"
            "Pérdida de Zx: {:.2f}%\n"
            "Yc Ideal: {:.6g}\n"
            "Yc Modificada: {:.6g}\n\n"
            "Clasificación: {}\n"
            "Dictamen: {}"
        ).format(
            area_loss, inertia_loss, zx_loss, self.ideal.yc, self.modified.yc,
            self.severity, self.recommendation
        )
        axis.text(
            0.05, 0.95, text, va="top", transform=axis.transAxes,
            bbox={"boxstyle": "round", "facecolor": "white", "edgecolor": severity_color,
                  "linewidth": 3},
        )
        axis.set_title("DICTAMEN")
        axis.axis("off")
