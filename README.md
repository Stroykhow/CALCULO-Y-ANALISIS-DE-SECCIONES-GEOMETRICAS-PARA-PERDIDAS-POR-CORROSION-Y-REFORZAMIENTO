# Bridge Section Analyzer

Bridge Section Analyzer es un software de consola y generación gráfica diseñado para evaluar el comportamiento geométrico y mecánico de secciones transversales compuestas utilizadas en puentes de vigas prefabricadas.

El proyecto compara dos alternativas de sección:

- Sección ideal: referencia base o 100% de capacidad.
- Sección modificada: sección evaluada, afectada por corrosión, pérdida de espesor, daño, reducción geométrica, reparación, reforzamiento o aumento de sección.

La herramienta permite cuantificar la diferencia entre ambas secciones mediante propiedades estructurales calculadas por la biblioteca analítica base ([sections.py](./sections.py)) y la lógica comparativa implementada en ([section_comparison.py](./section_comparison.py)).

## Objetivo

Analizar y comparar dos secciones compuestas para determinar, de forma automatizada, cómo afecta la modificación geométrica en:

- Área total
- Posición del centroide
- Eje neutro
- Momento de inercia
- Módulos resistentes
- Variación porcentual respecto a la sección ideal
- Severidad estructural según pérdida de capacidad

## Características principales

- Cálculo de propiedades geométricas de la sección ideal y modificada.
- Comparación usando la sección ideal como denominador.
- Fórmula de variación obligatoria:

  ((Modificada - Ideal) / Ideal) × 100

- Cálculo de capacidad relativa:

  (Modificada / Ideal) × 100

- Generación automática de tabla comparativa.
- Clasificación por severidad según pérdida de Zx.
- Gráficas Matplotlib con tres paneles:
  1. Geometría
  2. Desempeño
  3. Dictamen técnico
- Validación de entradas y control básico de errores.
- Pruebas automáticas para escenarios clave.

## Criterio de severidad

La severidad se define principalmente en función de la pérdida de Zx.

- Verde: pérdida Zx < 10% → MANTENIMIENTO PREVENTIVO
- Naranja: 10% ≤ pérdida Zx ≤ 25% → REDISEÑO DE SU CAPACIDAD NOMINAL
- Rojo: pérdida Zx > 25% → INTERVENCIÓN INMINENTE

## Estructura del proyecto

```text
Bridge-Section-Analyzer/
├── main.py
├── sections.py
├── section_comparison.py
├── requirements.txt
├── README.md
├── bridge_section_comparison.png
├── test_section_comparison.py
└── __pycache__/
```

## Requisitos

- Python 3.10 o superior
- NumPy
- Matplotlib

## Instalación

1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd Bridge-Section-Analyzer
```

2. Crear un entorno virtual

```bash
python -m venv .venv
```

En Linux/macOS:

```bash
source .venv/bin/activate
```

En Windows:

```bash
.venv\Scripts\activate
```

3. Instalar dependencias

```bash
pip install -r requirements.txt
```

## Ejecución

Ejecutar el ejemplo principal:

```bash
python main.py
```

Esto genera una comparación entre una sección ideal y una modificada, y guarda la gráfica resultante en:

```text
bridge_section_comparison.png
```

## Ejemplo de uso

El ejemplo base se encuentra en [main.py](./main.py):

```python
from section_comparison import SectionComparison
from sections import Deck

ideal = Deck(width=2.00, thickness=0.25)
modified = Deck(width=1.80, thickness=0.25)

comparison = SectionComparison(ideal, modified)

print("Área Ideal:", comparison.ideal.area)
print("Área Modificada:", comparison.modified.area)
print("Pérdida de área:", round(-comparison._value("area").variation_percent, 2), "%")
print("Clasificación:", comparison.severity)
print("Dictamen:", comparison.recommendation)

comparison.plot("bridge_section_comparison.png")
```

## Salida esperada

```text
=== Bridge Section Analyzer ===
Sección ideal: referencia 100%
Sección modificada: reducción geométrica

Área Ideal: 0.5
Área Modificada: 0.45
Pérdida de área: 10.0 %
Pérdida de inercia: 10.0 %
Pérdida de Zx: 10.0 %
Yc Ideal: 0.125
Yc Modificada: 0.125
Clasificación: NARANJA
Dictamen: REDISEÑO DE SU CAPACIDAD NOMINAL
```

## Aplicación técnica

Este tipo de análisis es útil para:

- evaluar pérdida de sección por corrosión o desgaste
- cuantificar daño geométrico en elementos estructurales
- comparar secciones originales y reparadas
- estimar capacidad residual de vigas o tableros
- apoyar decisiones de mantenimiento, reforzamiento o rediseño

## Nota

La lógica de cálculo geométrico y estructural se basa en las funciones ya existentes en la librería base. Las fórmulas matemáticas originales no se reemplazan; se reutilizan y se incorporan dentro del proceso de comparación ideal vs modificada.

## Licencia

Este proyecto se entrega con fines de análisis y desarrollo académico. Ajustar la licencia según el uso final deseado.
