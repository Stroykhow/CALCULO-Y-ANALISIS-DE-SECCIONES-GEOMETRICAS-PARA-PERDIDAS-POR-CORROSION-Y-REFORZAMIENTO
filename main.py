"""Programa interactivo para comparar dos secciones compuestas de puente."""

from section_comparison import SectionComparison
from sections import BulbTeeGirderBridge, Deck


def ask_float(prompt):
    while True:
        try:
            value = float(input(prompt).replace(",", "."))
            if value <= 0:
                raise ValueError
            return value
        except ValueError:
            print("Entrada inválida. Ingrese un valor numérico positivo.")


def build_bridge_section():
    print("\nIngrese las cotas de la SECCIÓN IDEAL")
    b1 = ask_float("b1 (m): ")
    b2 = ask_float("b2 (m): ")
    b3 = ask_float("b3 (m): ")
    b4 = ask_float("b4 (m): ")
    d1 = ask_float("d1 (m): ")
    d2 = ask_float("d2 (m): ")
    d3 = ask_float("d3 (m): ")
    d4 = ask_float("d4 (m): ")
    d5 = ask_float("d5 (m): ")
    d6 = ask_float("d6 (m): ")
    d7 = ask_float("d7 (m): ")
    t1 = ask_float("t1 (m): ")
    t2 = ask_float("t2 (m): ")
    c1 = ask_float("c1 (m): ")
    return BulbTeeGirderBridge(b1, b2, b3, b4, d1, d2, d3, d4, d5, d6, d7, t1, t2, c1)


def build_modified_section():
    print("\nIngrese las cotas de la SECCIÓN A COMPARAR")
    b1 = ask_float("b1 (m): ")
    b2 = ask_float("b2 (m): ")
    b3 = ask_float("b3 (m): ")
    b4 = ask_float("b4 (m): ")
    d1 = ask_float("d1 (m): ")
    d2 = ask_float("d2 (m): ")
    d3 = ask_float("d3 (m): ")
    d4 = ask_float("d4 (m): ")
    d5 = ask_float("d5 (m): ")
    d6 = ask_float("d6 (m): ")
    d7 = ask_float("d7 (m): ")
    t1 = ask_float("t1 (m): ")
    t2 = ask_float("t2 (m): ")
    c1 = ask_float("c1 (m): ")
    return BulbTeeGirderBridge(b1, b2, b3, b4, d1, d2, d3, d4, d5, d6, d7, t1, t2, c1)


def main():
    print("=== Bridge Section Analyzer ===")
    ideal = build_bridge_section()
    modified = build_modified_section()

    comparison = SectionComparison(ideal, modified)

    print("\n=== RESULTADOS ===")
    print("Área Ideal:", round(comparison.ideal.area, 4))
    print("Área Modificada:", round(comparison.modified.area, 4))
    print("Pérdida de área:", round(-comparison._value("area").variation_percent, 2), "%")
    print("Pérdida de inercia:", round(-comparison._value("ixx").variation_percent, 2), "%")
    print("Pérdida de Zx:", round(-comparison._value("zx_critical").variation_percent, 2), "%")
    print("Yc Ideal:", comparison.ideal.yc)
    print("Yc Modificada:", comparison.modified.yc)
    print("Clasificación:", comparison.severity)
    print("Dictamen:", comparison.recommendation)
    print()

    print("TABLA COMPARATIVA")
    for row in comparison.table_rows():
        print(
            row["Propiedad"],
            "| Ideal:", round(row["Ideal"], 6),
            "| Modificada:", round(row["Modificada"], 6),
            "| Diferencia:", round(row["Diferencia"], 6),
            "| Variación:", round(row["Variación (%)"], 2), "%"
        )

    print()
    print("Generando gráficos de comparación...")
    fig, axes = comparison.plot("bridge_section_comparison.png")
    print("Gráfico guardado en: bridge_section_comparison.png")
    fig.clf()


if __name__ == "__main__":
    main()
