"""Vista «Cálculo»: formulario de entrada, validación, resultados y gráficas."""

import flet as ft

from app import db, graficas, modelo
from app.ui.compat import avisar, boton, imagen_png
from app.ui.utilidades import COLOR_SEVERIDAD, generar_y_abrir_memoria
from app.validacion import leer_numero


class VistaCalculo:
    """Construye y gestiona la vista de cálculo."""

    def __init__(self, page, conexion, al_guardar=None):
        self.page = page
        self.conexion = conexion
        self.al_guardar = al_guardar          # callback para refrescar el historial
        self.resultado = None
        self.calculo_id = None                # id en SQLite del cálculo mostrado
        self.tipo = modelo.EJEMPLO["tipo"]

        self.txt_proyecto = ft.TextField(label="Proyecto (puente / estructura)", width=320)
        self.txt_nombre = ft.TextField(label="Nombre del cálculo (p. ej. Viga 3 - eje B)",
                                       width=320)
        self.txt_autores = ft.TextField(label="Elaboró (autores de la memoria)", width=320)
        self.txt_edad = ft.TextField(
            label="Edad de la estructura en la inspección (años) — opcional", width=420,
            keyboard_type=ft.KeyboardType.NUMBER)
        self.grupo_tipo = ft.RadioGroup(
            value=self.tipo, on_change=self._cambiar_tipo,
            content=ft.Row([ft.Radio(value=k, label=v) for k, v in modelo.NOMBRES_TIPO.items()]),
        )
        self.campos = {}
        self.formulario = ft.Row(spacing=30, vertical_alignment=ft.CrossAxisAlignment.START)
        self._crear_campos()

        self.banner = ft.Container()
        self.tabla = ft.Column()
        self.graficas = ft.Row(wrap=True, spacing=10)

        self.control = ft.Column(
            expand=True, scroll=ft.ScrollMode.AUTO, spacing=12,
            controls=[
                ft.Text("Comparación de sección ideal vs. sección modificada",
                        size=20, weight=ft.FontWeight.BOLD),
                ft.Text("Ingrese las cotas en metros. La sección modificada representa el "
                        "estado inspeccionado (pérdida por corrosión) o reforzado."),
                ft.Row([self.txt_proyecto, self.txt_nombre, self.txt_autores], wrap=True),
                self.grupo_tipo,
                self.formulario,
                self.txt_edad,
                ft.Row(wrap=True, controls=[
                    boton("Calcular", self._on_calcular, ft.Icons.CALCULATE),
                    boton("Guardar en historial", self._on_guardar, ft.Icons.SAVE, "outlined"),
                    boton("Generar memoria .docx", self._on_memoria, ft.Icons.DESCRIPTION,
                          "outlined"),
                    boton("Cargar ejemplo", self._on_ejemplo, ft.Icons.AUTO_FIX_HIGH, "text"),
                    boton("Limpiar", self._on_limpiar, ft.Icons.CLEAR, "text"),
                ]),
                ft.Divider(),
                self.banner,
                self.tabla,
                self.graficas,
            ],
        )

    # ------------------------------------------------------------------ formulario
    def _crear_campos(self, valores_ideal=None, valores_mod=None):
        """(Re)crea los campos de entrada para el tipo de sección seleccionado."""
        self.campos = {"ideal": {}, "mod": {}}
        columnas = []
        for lado, titulo, valores in (("ideal", "Sección ideal (diseño)", valores_ideal),
                                      ("mod", "Sección modificada (inspección)", valores_mod)):
            filas = [ft.Text(titulo, weight=ft.FontWeight.BOLD)]
            for clave, descripcion, unidad in modelo.PARAMETROS[self.tipo]:
                campo = ft.TextField(
                    label=f"{clave} ({unidad})", hint_text=descripcion, tooltip=descripcion,
                    width=220, keyboard_type=ft.KeyboardType.NUMBER,
                    value="" if not valores else f"{valores[clave]:g}",
                )
                self.campos[lado][clave] = campo
                filas.append(campo)
            columnas.append(ft.Column(filas, spacing=6))
        self.formulario.controls = columnas

    def _cambiar_tipo(self, e):
        self.tipo = self.grupo_tipo.value
        self._crear_campos()
        self._limpiar_resultados()
        self.page.update()

    def _leer_entradas(self):
        """Lee y valida los campos. Devuelve (ideal, mod, edad) o None si hay errores."""
        valores, hay_error = {"ideal": {}, "mod": {}}, False
        for lado, campos in self.campos.items():
            for clave, campo in campos.items():
                valor, error = leer_numero(campo.value, positivo=True)
                campo.error_text = error
                hay_error |= error is not None
                valores[lado][clave] = valor
        edad, error = leer_numero(self.txt_edad.value, positivo=True, obligatorio=False)
        self.txt_edad.error_text = error
        hay_error |= error is not None
        self.page.update()
        if hay_error:
            avisar(self.page, "Revise los campos marcados en rojo.", error=True)
            return None
        return valores["ideal"], valores["mod"], edad

    # ------------------------------------------------------------------ acciones
    def calcular(self):
        """Valida, calcula y muestra resultados. Devuelve el Resultado o None."""
        entradas = self._leer_entradas()
        if entradas is None:
            return None
        ideal, mod, edad = entradas
        try:
            self.resultado = modelo.comparar(self.tipo, ideal, mod, edad)
        except ValueError as error:
            avisar(self.page, f"Geometría no válida: {error}", error=True)
            return None
        self._mostrar_resultados()
        return self.resultado

    def _on_calcular(self, e):
        self.calculo_id = None
        if self.calcular():
            avisar(self.page, "Cálculo realizado.")

    def _on_guardar(self, e):
        if not self.txt_proyecto.value or not self.txt_proyecto.value.strip():
            self.txt_proyecto.error_text = "Obligatorio para guardar"
            self.page.update()
            avisar(self.page, "Indique el nombre del proyecto.", error=True)
            return
        if not self.txt_nombre.value or not self.txt_nombre.value.strip():
            self.txt_nombre.error_text = "Obligatorio para guardar"
            self.page.update()
            avisar(self.page, "Indique el nombre del cálculo.", error=True)
            return
        self.txt_proyecto.error_text = self.txt_nombre.error_text = None
        resultado = self.calcular()
        if resultado is None:
            return
        self.calculo_id = db.guardar_calculo(
            self.conexion, self.txt_proyecto.value, self.txt_nombre.value, resultado,
            resultado.proyeccion.edad_anios)
        avisar(self.page, f"Cálculo guardado con id {self.calculo_id}.")
        if self.al_guardar:
            self.al_guardar()

    def _on_memoria(self, e):
        if self.calculo_id is None:
            avisar(self.page, "Guarde el cálculo antes de generar la memoria "
                              "(o genérela desde el Historial).", error=True)
            return
        generar_y_abrir_memoria(self.page, self.conexion, self.calculo_id, self.autores())

    def _on_ejemplo(self, e):
        self.tipo = modelo.EJEMPLO["tipo"]
        self.grupo_tipo.value = self.tipo
        self._crear_campos(modelo.EJEMPLO["ideal"], modelo.EJEMPLO["modificada"])
        self.txt_edad.value = f"{modelo.EJEMPLO['edad_anios']:g}"
        self.txt_proyecto.value = self.txt_proyecto.value or "Puente ejemplo"
        self.txt_nombre.value = self.txt_nombre.value or "Viga exterior - inspección"
        self.calculo_id = None
        self.calcular()

    def _on_limpiar(self, e):
        self._crear_campos()
        for campo in (self.txt_edad, self.txt_nombre):
            campo.value, campo.error_text = "", None
        self.calculo_id = None
        self._limpiar_resultados()
        self.page.update()

    def autores(self):
        return (self.txt_autores.value or "").strip()

    def cargar_calculo(self, calculo):
        """Reabre en el formulario un cálculo guardado en el historial."""
        self.tipo = calculo["tipo_seccion"]
        self.grupo_tipo.value = self.tipo
        self._crear_campos(calculo["param_ideal"], calculo["param_mod"])
        self.txt_proyecto.value = calculo["proyecto"]
        self.txt_nombre.value = calculo["nombre"]
        edad = calculo.get("edad_anios")
        self.txt_edad.value = f"{edad:g}" if edad else ""
        if self.calcular():
            self.calculo_id = calculo["id"]

    # ------------------------------------------------------------------ resultados
    def _limpiar_resultados(self):
        self.resultado = None
        self.banner.content = None
        self.tabla.controls = []
        self.graficas.controls = []

    def _mostrar_resultados(self):
        r = self.resultado
        self.banner.content = ft.Container(
            bgcolor=COLOR_SEVERIDAD[r.severidad], border_radius=8, padding=14,
            content=ft.Column(spacing=4, controls=[
                ft.Text(f"{r.severidad} — {r.dictamen}", size=18,
                        weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Text(f"Pérdida de área: {r.perdida_area:.2f} %   ·   Pérdida de Ixx: "
                        f"{r.perdida_ixx:.2f} %   ·   Pérdida de Zx: {r.perdida_zx:.2f} %   ·   "
                        f"Chequeo Zx ≥ 90 %: {'CUMPLE' if r.cumple else 'NO CUMPLE'}",
                        color=ft.Colors.WHITE),
                ft.Text(self._texto_proyeccion(), color=ft.Colors.WHITE),
            ]),
        )
        self.tabla.controls = [ft.DataTable(
            columns=[ft.DataColumn(ft.Text(t)) for t in
                     ("Propiedad", "Unidad", "Ideal", "Modificada", "Variación (%)")],
            rows=[ft.DataRow(cells=[
                ft.DataCell(ft.Text(f["propiedad"])), ft.DataCell(ft.Text(f["unidad"])),
                ft.DataCell(ft.Text(f"{f['ideal']:.6g}")),
                ft.DataCell(ft.Text(f"{f['modificada']:.6g}")),
                ft.DataCell(ft.Text("—" if f["clave"] in ("xc", "ixy")
                                    else f"{f['variacion']:+.2f}")),
            ]) for f in r.filas_tabla()],
        )]
        self.graficas.controls = [
            imagen_png(graficas.figura_a_png(graficas.figura_geometria(r)), width=560),
            imagen_png(graficas.figura_a_png(graficas.figura_capacidad(r)), width=640),
        ]
        self.page.update()

    def _texto_proyeccion(self):
        proy = self.resultado.proyeccion
        partes = []
        for umbral in (modelo.UMBRAL_PREVENTIVO, modelo.UMBRAL_INTERVENCION):
            a, t = proy.alfa_umbral.get(umbral), proy.tiempo_umbral(umbral)
            if a is None:
                partes.append(f"umbral {umbral:.0f} %: no se alcanza")
            elif t is not None:
                partes.append(f"umbral {umbral:.0f} %: α = {a:.2f} → {t:.1f} años "
                              f"(remanente {t - proy.edad_anios:.1f} años)")
            else:
                partes.append(f"umbral {umbral:.0f} %: α = {a:.2f}")
        return "Proyección (brentq): " + "   ·   ".join(partes)
