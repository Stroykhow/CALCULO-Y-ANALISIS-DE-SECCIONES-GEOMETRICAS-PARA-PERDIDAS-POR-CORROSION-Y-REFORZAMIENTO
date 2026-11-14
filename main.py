"""Punto de entrada: python main.py  (o  flet run)."""

import matplotlib

matplotlib.use("Agg")  # las figuras se dibujan en memoria, sin ventanas de Matplotlib

from app.ui.app import main  # noqa: E402
from app.ui.compat import ejecutar  # noqa: E402

if __name__ == "__main__":
    ejecutar(main)
