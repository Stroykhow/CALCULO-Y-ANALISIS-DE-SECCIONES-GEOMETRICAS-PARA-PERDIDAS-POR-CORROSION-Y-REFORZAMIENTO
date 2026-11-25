"""Vista «Cálculo»: formulario de entrada, validación, resultados y gráficas.

Diseño responsive: en pantallas anchas el formulario queda a la izquierda y los
resultados a la derecha; en pantallas angostas se apilan uno debajo del otro.
"""

import flet as ft

from app import db, flexion, graficas, modelo
from app.ui import estilos as es
from app.ui.compat import AJUSTE_CONTENER, _acepta, avisar, boton, imagen_png
from app.ui.utilidades import generar_y_abrir_memoria
from app.validacion import leer_numero


# Colores de la tarjeta de datos de entrada (azul marino con acentos celestes)
FONDO_ENTRADA = "#0F2A44"
BORDE_ENTRADA = "#1F4A70"
SOBRE_ENTRADA = "#FFFFFF"
SUAVE_ENTRADA = "#9FD8F7"


def _estilo_campo():
    """Estilo de los TextField sobre la tarjeta de entrada (solo opciones que existan)."""
    estilo = dict(
        filled=True, bgcolor="#33000000", border_color="#8CFFFFFF",
        focused_border_color=es.AZUL, color=SOBRE_ENTRADA, cursor_color=SOBRE_ENTRADA,
        label_style=ft.TextStyle(color=SUAVE_ENTRADA),
        hint_style=ft.TextStyle(color="#99FFFFFF"),
        error_style=ft.TextStyle(color="#FFF176", weight=ft.FontWeight.W_600),
    )
    return {k: v for k, v in estilo.items() if _acepta(ft.TextField, k)}


def _marcar(campo, error, etiqueta, errores):
    """Marca un campo en rojo si tiene error y agrega el mensaje a la lista."""
    campo.error_text = error
    campo.border_color = "#FF5252" if error else "#8CFFFFFF"
    campo.focused_border_color = "#FF5252" if error else es.AZUL
    if error:
        errores.append(f"{etiqueta}: {error}")


def _estilo_boton(fondo, texto, borde=None):
    lado = {"side": ft.BorderSide(1.5, borde)} if borde else {}
    return ft.ButtonStyle(bgcolor=fondo, color=texto, **lado)


def _campo_numero(valor="", unidad="m"):
    """TextField compacto para un número, con la unidad dentro del campo."""
    extra = _estilo_campo()
    if _acepta(ft.TextField, "suffix_text"):
        extra["suffix_text"] = unidad
    elif _acepta(ft.TextField, "suffix"):
        extra["suffix"] = unidad
    return ft.TextField(value=valor, expand=2, dense=True, text_size=14,
                        keyboard_type=ft.KeyboardType.NUMBER, border_radius=8,
                        hint_text="0.00", **extra)


class VistaCalculo:
    """Construye y gestiona la vista de cálculo."""

    def __init__(self, page, conexion, al_guardar=None):
        self.page = page
        self.conexion = conexion
        self.al_guardar = al_guardar          # callback para refrescar el historial
        self.resultado = None
        self.calculo_id = None                # id en SQLite del cálculo mostrado
        self.tipo = modelo.EJEMPLO["tipo"]

        def texto(etiqueta, col):
            return ft.TextField(label=etiqueta, dense=True, border_radius=8, col=col,
                                **_estilo_campo())

        self.txt_proyecto = texto("Proyecto (puente / estructura)", {"xs": 12, "sm": 6})
        self.txt_nombre = texto("Nombre del cálculo", {"xs": 12, "sm": 6})
        self.txt_autores = texto("Elaboró (autores de la memoria)", {"xs": 12})
        self.txt_edad = ft.TextField(label="Edad en la inspección (años) — opcional",
                                     dense=True, border_radius=8,
                                     keyboard_type=ft.KeyboardType.NUMBER, **_estilo_campo())
        self.grupo_tipo = ft.RadioGroup(
            value=self.tipo, on_change=self._cambiar_tipo,
            content=ft.Column([ft.Radio(value=k, label=v, fill_color=es.AZUL)
                               for k, v in modelo.NOMBRES_TIPO.items()], spacing=0),
        )
        self.campos = {}
        self.filas_cotas = ft.Column(spacing=6)
        self._crear_campos()

        # --- Flexión: materiales, refuerzo y cargas ---------------------------
        def numero(etiqueta, col, valor=""):
            return ft.TextField(label=etiqueta, value=valor, dense=True, border_radius=8,
                                col=col, keyboard_type=ft.KeyboardType.NUMBER,
                                **_estilo_campo())

        mitad, tercio = {"xs": 12, "sm": 6}, {"xs": 12, "sm": 4}
        self.txt_fc = numero("f'c concreto (MPa)", tercio, "28")
        self.txt_fy = numero("fy acero (MPa)", tercio, "420")
        self.txt_perdida_acero = numero("Pérdida de acero por corrosión (%)", tercio, "0")
        self.txt_luz = numero("Luz de la viga L (m)", tercio)
        self.txt_cm = numero("Carga muerta adicional D (kN/m)", tercio)
        self.txt_cv = numero("Carga viva L (kN/m)", tercio)
        self.capas = []                       # lista de dicts con los 3 campos de cada capa
        self.filas_capas = ft.Column(spacing=6)
        self._crear_capas([None])
        extra = {"fill_color": es.AZUL} if _acepta(ft.Checkbox, "fill_color") else {}
        self.chk_flexion = ft.Checkbox(label="Evaluar a flexión (NSR-10)", value=True,
                                       on_change=self._cambiar_flexion, **extra)
        self.bloque_flexion = ft.Column(spacing=10, controls=[
            ft.ResponsiveRow([self.txt_fc, self.txt_fy, self.txt_perdida_acero],
                             spacing=10, run_spacing=10),
            ft.Row([
                ft.Text("Barras", expand=2, size=12.5, color=SOBRE_ENTRADA,
                        weight=ft.FontWeight.W_600),
                ft.Text("Ø (mm)", expand=2, size=12.5, color=SOBRE_ENTRADA,
                        weight=ft.FontWeight.W_600),
                ft.Text("y desde la base (m)", expand=3, size=12.5, color=SOBRE_ENTRADA,
                        weight=ft.FontWeight.W_600),
                ft.Container(width=40),
            ]),
            self.filas_capas,
            ft.Row(wrap=True, controls=[
                boton("Agregar capa", self._on_agregar_capa, ft.Icons.ADD, "text",
                      style=_estilo_boton(None, SOBRE_ENTRADA)),
                ft.Text("Ø: No.4 = 12.7 · No.5 = 15.9 · No.6 = 19.1 · No.8 = 25.4 mm",
                        size=11.5, color=SUAVE_ENTRADA),
            ]),
            ft.ResponsiveRow([self.txt_luz, self.txt_cm, self.txt_cv],
                             spacing=10, run_spacing=10),
            ft.Text("Viga simplemente apoyada. El peso propio se suma solo (área × 24 kN/m³). "
                    "Mu = (1.2D + 1.6L)·L²/8.", size=11.5, color=SUAVE_ENTRADA),
        ])

        formulario = es.tarjeta(
            es.titulo("Datos de entrada", ft.Icons.EDIT_NOTE,
                      "La sección modificada es el estado inspeccionado (corrosión) o reforzado.",
                      color=SOBRE_ENTRADA, acento=es.AZUL, color_sub=SUAVE_ENTRADA),
            es.etiqueta_seccion("Identificación", SUAVE_ENTRADA),
            ft.ResponsiveRow([self.txt_proyecto, self.txt_nombre, self.txt_autores],
                             spacing=10, run_spacing=10),
            es.etiqueta_seccion("Tipo de sección", SUAVE_ENTRADA),
            self.grupo_tipo,
            es.etiqueta_seccion("Cotas de la sección", SUAVE_ENTRADA),
            ft.Row([
                ft.Text("Cota", expand=3, size=12.5, color=SUAVE_ENTRADA),
                ft.Text("Ideal", expand=2, size=12.5, color=SOBRE_ENTRADA,
                        weight=ft.FontWeight.W_600),
                ft.Text("Modificada", expand=2, size=12.5, color=SOBRE_ENTRADA,
                        weight=ft.FontWeight.W_600),
            ]),
            self.filas_cotas,
            es.etiqueta_seccion("Proyección en el tiempo", SUAVE_ENTRADA),
            self.txt_edad,
            es.etiqueta_seccion("Acero de refuerzo y cargas", SUAVE_ENTRADA),
            self.chk_flexion,
            self.bloque_flexion,
            ft.ResponsiveRow(spacing=10, run_spacing=10, controls=[
                ft.Container(boton("Calcular", self._on_calcular, ft.Icons.CALCULATE,
                                   style=_estilo_boton(es.AZUL, es.TEXTO_OSCURO)),
                             col={"xs": 12, "sm": 6}),
                ft.Container(boton("Guardar", self._on_guardar, ft.Icons.SAVE, "outlined",
                                   style=_estilo_boton(None, SOBRE_ENTRADA, SOBRE_ENTRADA)),
                             col={"xs": 12, "sm": 6}),
                ft.Container(boton("Generar memoria .docx", self._on_memoria,
                                   ft.Icons.DESCRIPTION, "outlined",
                                   style=_estilo_boton(None, SOBRE_ENTRADA, SOBRE_ENTRADA)),
                             col={"xs": 12}),
            ]),
            ft.Row([boton("Cargar ejemplo", self._on_ejemplo, ft.Icons.AUTO_FIX_HIGH, "text",
                          style=_estilo_boton(None, SOBRE_ENTRADA)),
                    boton("Limpiar", self._on_limpiar, ft.Icons.CLEAR_ALL, "text",
                          style=_estilo_boton(None, SOBRE_ENTRADA))],
                   wrap=True),
            col={"xs": 12, "lg": 5, "xl": 4},
            bgcolor=FONDO_ENTRADA, color_borde=BORDE_ENTRADA, sombra="#4027B0F5",
        )

        self.panel_resultados = ft.Column(spacing=16, col={"xs": 12, "lg": 7, "xl": 8})
        self._mostrar_vacio()

        self.control = ft.Column(
            expand=True, scroll=ft.ScrollMode.AUTO,
            controls=[ft.ResponsiveRow([formulario, self.panel_resultados],
                                       spacing=20, run_spacing=20)],
        )

    # ------------------------------------------------------------------ formulario
    def _crear_campos(self, valores_ideal=None, valores_mod=None):
        """(Re)crea las filas de cotas para el tipo de sección seleccionado."""
        self.campos = {"ideal": {}, "mod": {}}
        filas = []
        for clave, descripcion, unidad in modelo.PARAMETROS[self.tipo]:
            ideal = _campo_numero(f"{valores_ideal[clave]:g}" if valores_ideal else "", unidad)
            mod = _campo_numero(f"{valores_mod[clave]:g}" if valores_mod else "", unidad)
            self.campos["ideal"][clave], self.campos["mod"][clave] = ideal, mod
            filas.append(ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.START, spacing=8,
                controls=[
                    ft.Column([ft.Text(clave, weight=ft.FontWeight.BOLD, size=14,
                                       color=SOBRE_ENTRADA),
                               ft.Text(descripcion, size=11.5, color=SUAVE_ENTRADA)],
                              spacing=0, expand=3),
                    ideal, mod,
                ]))
        self.filas_cotas.controls = filas

    def _cambiar_tipo(self, e):
        self.tipo = self.grupo_tipo.value
        self._crear_campos()
        self.calculo_id = None
        self._mostrar_vacio()
        self.page.update()

    def _crear_capas(self, capas):
        """(Re)crea las filas de capas de acero. ``capas``: lista de Capa o None (vacía)."""
        self.capas = []
        self.filas_capas.controls = []
        for capa in capas:
            self._agregar_fila_capa(capa)

    def _agregar_fila_capa(self, capa=None):
        def campo(valor, expand):
            return ft.TextField(value=valor, expand=expand, dense=True, text_size=14,
                                border_radius=8, keyboard_type=ft.KeyboardType.NUMBER,
                                **_estilo_campo())

        fila_campos = dict(
            n=campo(f"{capa.n_barras}" if capa else "", 2),
            diametro=campo(f"{capa.diametro_mm:g}" if capa else "", 2),
            y=campo(f"{capa.y:g}" if capa else "", 3),
        )
        fila = ft.Row(vertical_alignment=ft.CrossAxisAlignment.START, spacing=8)
        fila.controls = [fila_campos["n"], fila_campos["diametro"], fila_campos["y"],
                         ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=SUAVE_ENTRADA,
                                       tooltip="Quitar capa",
                                       on_click=lambda e, f=fila: self._quitar_capa(f))]
        fila_campos["fila"] = fila
        self.capas.append(fila_campos)
        self.filas_capas.controls.append(fila)

    def _on_agregar_capa(self, e):
        self._agregar_fila_capa()
        self.page.update()

    def _quitar_capa(self, fila):
        self.capas = [c for c in self.capas if c["fila"] is not fila]
        self.filas_capas.controls = [c["fila"] for c in self.capas]
        if not self.capas:
            self._agregar_fila_capa()
        self.page.update()

    def _cambiar_flexion(self, e):
        self.bloque_flexion.visible = bool(self.chk_flexion.value)
        self.page.update()

    def _llenar_flexion(self, datos):
        """Pone en el formulario un DatosFlexion (o lo desactiva si es None)."""
        self.chk_flexion.value = datos is not None
        self.bloque_flexion.visible = datos is not None
        if datos is None:
            return
        for campo, valor in ((self.txt_fc, datos.fc), (self.txt_fy, datos.fy),
                             (self.txt_perdida_acero, datos.perdida_acero),
                             (self.txt_luz, datos.luz), (self.txt_cm, datos.carga_muerta),
                             (self.txt_cv, datos.carga_viva)):
            campo.value, campo.error_text = f"{valor:g}", None
        self._crear_capas(datos.capas)

    def _leer_flexion(self, errores):
        """Lee los datos de flexión. Devuelve DatosFlexion, o None si está desactivada."""
        if not self.chk_flexion.value:
            return None
        valores = {}
        for clave, campo, etiqueta, obligatorio, positivo in (
            ("fc", self.txt_fc, "f'c", True, True),
            ("fy", self.txt_fy, "fy", True, True),
            ("perdida_acero", self.txt_perdida_acero, "Pérdida de acero", False, False),
            ("luz", self.txt_luz, "Luz de la viga", True, True),
            ("carga_muerta", self.txt_cm, "Carga muerta", False, False),
            ("carga_viva", self.txt_cv, "Carga viva", False, False),
        ):
            valor, error = leer_numero(campo.value, positivo=positivo, obligatorio=obligatorio)
            if error is None and valor is not None and valor < 0:
                error = "No puede ser negativo"
            _marcar(campo, error, etiqueta, errores)
            valores[clave] = valor or 0.0
        if self.txt_perdida_acero.error_text is None and valores["perdida_acero"] >= 100:
            _marcar(self.txt_perdida_acero, "Debe ser menor que 100", "Pérdida de acero",
                    errores)

        capas = []
        for i, fila in enumerate(self.capas, start=1):
            n, e_n = leer_numero(fila["n"].value)
            if e_n is None and n != int(n):
                e_n = "Debe ser un número entero"
            diametro, e_d = leer_numero(fila["diametro"].value)
            y, e_y = leer_numero(fila["y"].value)
            _marcar(fila["n"], e_n, f"Capa {i}, barras", errores)
            _marcar(fila["diametro"], e_d, f"Capa {i}, Ø", errores)
            _marcar(fila["y"], e_y, f"Capa {i}, y", errores)
            if not (e_n or e_d or e_y):
                capas.append(flexion.Capa(int(n), diametro, y))
        return flexion.DatosFlexion(capas=capas, **valores)

    
    def _leer_entradas(self):
        """Valida datos y muestra las casillas incorrectas."""
        valores = {"ideal": {}, "mod": {}}
        errores = []

        for lado, campos in self.campos.items():
            nombre_lado = "Ideal" if lado == "ideal" else "Modificada"

            for clave, campo in campos.items():
                valor, error = leer_numero(
                    campo.value, positivo=True
                )

                campo.error_text = error
                campo.border_color = (
                    "#FF5252" if error else "#8CFFFFFF"
                )
                campo.focused_border_color = (
                    "#FF5252" if error else es.AZUL
                )

                if error:
                    errores.append(
                        f"{clave} ({nombre_lado}): {error}"
                    )

                valores[lado][clave] = valor

        edad, error = leer_numero(
            self.txt_edad.value,
            positivo=True,
            obligatorio=False
        )

        self.txt_edad.error_text = error
        self.txt_edad.border_color = (
            "#FF5252" if error else "#8CFFFFFF"
        )
        self.txt_edad.focused_border_color = (
            "#FF5252" if error else es.AZUL
        )

        if error:
            errores.append(
                f"Edad de inspección: {error}"
            )

        datos_flexion = self._leer_flexion(errores)

        self.page.update()

        if errores:
            detalle = "\n".join(
                f"• {mensaje}" for mensaje in errores
            )

            avisar(
                self.page,
                f"Se encontraron {len(errores)} errores:\n{detalle}",
                error=True
            )
            return None

        return valores["ideal"], valores["mod"], edad, datos_flexion


    # ------------------------------------------------------------------ acciones
    def calcular(self):
        """Valida, calcula y muestra resultados. Devuelve el Resultado o None."""
        entradas = self._leer_entradas()
        if entradas is None:
            return None
        ideal, mod, edad, datos_flexion = entradas
        try:
            self.resultado = modelo.comparar(self.tipo, ideal, mod, edad, datos_flexion)
        except ValueError as error:
            avisar(self.page, f"Datos no válidos: {error}", error=True)
            return None
        self._mostrar_resultados()
        return self.resultado

    def _on_calcular(self, e):
        self.calculo_id = None
        if self.calcular():
            avisar(self.page, "Cálculo realizado.")

    def _on_guardar(self, e):
        faltantes = False
        for campo in (self.txt_proyecto, self.txt_nombre):
            vacio = not (campo.value or "").strip()
            campo.error_text = "Obligatorio para guardar" if vacio else None
            faltantes |= vacio
        if faltantes:
            self.page.update()
            avisar(self.page, "Indique el proyecto y el nombre del cálculo.", error=True)
            return
        resultado = self.calcular()
        if resultado is None:
            return
        self.calculo_id = db.guardar_calculo(
            self.conexion, self.txt_proyecto.value, self.txt_nombre.value, resultado,
            resultado.proyeccion.edad_anios)
        avisar(self.page, f"Cálculo guardado en el historial (id {self.calculo_id}).")
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
        self._llenar_flexion(flexion.EJEMPLO)
        self.txt_proyecto.value = self.txt_proyecto.value or "Puente ejemplo"
        self.txt_nombre.value = self.txt_nombre.value or "Viga exterior - inspección"
        self.calculo_id = None
        self.calcular()

    def _on_limpiar(self, e):
        self._crear_campos()
        for campo in (self.txt_edad, self.txt_nombre, self.txt_luz, self.txt_cm, self.txt_cv):
            campo.value, campo.error_text = "", None
        self._crear_capas([None])
        self.calculo_id = None
        self._mostrar_vacio()
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
        datos = None
        if calculo.get("datos_flexion") and calculo.get("capas"):
            datos = flexion.DatosFlexion.desde_diccionario(calculo["datos_flexion"],
                                                          calculo["capas"])
        self._llenar_flexion(datos)
        if self.calcular():
            self.calculo_id = calculo["id"]

    # ------------------------------------------------------------------ resultados
    def _mostrar_vacio(self):
        self.resultado = None
        self.panel_resultados.controls = [es.estado_vacio(
            ft.Icons.ARCHITECTURE, "Aún no hay resultados",
            "Ingrese las cotas de ambas secciones y pulse «Calcular», "
            "o use «Cargar ejemplo» para ver un caso completo.")]

    def _mostrar_resultados(self):
        r = self.resultado
        color, fondo, icono = es.SEVERIDAD[r.severidad]

        banner = ft.Container(
            padding=18, border_radius=14, bgcolor=fondo, border=es.borde(1, color),
            content=ft.Row(spacing=16, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                           controls=[
                ft.Icon(icono, color=color, size=44),
                ft.Column(spacing=2, expand=True, controls=[
                    ft.Text(f"Clasificación {r.severidad}", size=13, color=color,
                            weight=ft.FontWeight.W_600),
                    ft.Text(r.dictamen, size=20, weight=ft.FontWeight.BOLD, color=es.TEXTO),
                    ft.Text(f"Pérdida del módulo resistente crítico Zx: {r.perdida_zx:.2f} %",
                            size=13, color=es.TEXTO_SUAVE),
                ]),
                es.chip("CUMPLE" if r.cumple else "NO CUMPLE", es.TARJETA,
                        es.SEVERIDAD["VERDE" if r.cumple else "ROJO"][0]),
            ]),
        )

        def color_perdida(valor):
            if valor <= 0:
                return es.SEVERIDAD["VERDE"][0]
            return es.SEVERIDAD[modelo.clasificar(valor)[0]][0]

        proy = r.proyeccion
        t10 = proy.tiempo_umbral(modelo.UMBRAL_PREVENTIVO)
        if t10 is not None:
            remanente = max(t10 - proy.edad_anios, 0.0)
            vida = es.indicador("Vida hasta 10 % de pérdida", f"{remanente:.1f}", "años",
                                col={"xs": 6, "md": 3}, detalle=f"Ocurre a los {t10:.1f} años")
        else:
            a10 = proy.alfa_umbral.get(modelo.UMBRAL_PREVENTIVO)
            vida = es.indicador("Daño para 10 % de pérdida",
                                f"{a10:.2f}" if a10 is not None else "—", "α",
                                col={"xs": 6, "md": 3},
                                detalle="Indique la edad para verlo en años"
                                if a10 is not None else "No se alcanza")

        indicadores = ft.ResponsiveRow(spacing=12, run_spacing=12, controls=[
            es.indicador("Pérdida de área", f"{r.perdida_area:.2f}", "%",
                         color_perdida(r.perdida_area), {"xs": 6, "md": 3}),
            es.indicador("Pérdida de inercia Ixx", f"{r.perdida_ixx:.2f}", "%",
                         color_perdida(r.perdida_ixx), {"xs": 6, "md": 3}),
            es.indicador("Pérdida de Zx", f"{r.perdida_zx:.2f}", "%",
                         color_perdida(r.perdida_zx), {"xs": 6, "md": 3}),
            vida,
        ])

        figuras = ft.ResponsiveRow(spacing=16, run_spacing=16, controls=[
            es.tarjeta(es.titulo("Geometría", ft.Icons.SQUARE_FOOT),
                       imagen_png(graficas.figura_a_png(graficas.figura_geometria(r, oscuro=True)),
                                  fit=AJUSTE_CONTENER),
                       col={"xs": 12, "xl": 5}, padding=14),
            es.tarjeta(es.titulo("Proyección de la capacidad", ft.Icons.SHOW_CHART,
                                 self._texto_proyeccion()),
                       imagen_png(graficas.figura_a_png(graficas.figura_capacidad(r, oscuro=True)),
                                  fit=AJUSTE_CONTENER),
                       col={"xs": 12, "xl": 7}, padding=14),
        ])

        tabla = ft.DataTable(
            heading_row_color=es.PRIMARIO_CLARO, column_spacing=28,
            columns=[ft.DataColumn(ft.Text(t, weight=ft.FontWeight.W_600)) for t in
                     ("Propiedad", "Unidad", "Ideal", "Modificada", "Variación (%)")],
            rows=[ft.DataRow(cells=[
                ft.DataCell(ft.Text(f["propiedad"])), ft.DataCell(ft.Text(f["unidad"])),
                ft.DataCell(ft.Text(f"{f['ideal']:.6g}")),
                ft.DataCell(ft.Text(f"{f['modificada']:.6g}")),
                ft.DataCell(ft.Text(
                    "—" if f["clave"] in ("xc", "ixy") else f"{f['variacion']:+.2f}",
                    color=(es.TEXTO if f["clave"] in ("xc", "ixy", "yc") or
                           abs(f["variacion"]) < 1e-9 else
                           es.SEVERIDAD["ROJO" if f["variacion"] < 0 else "VERDE"][0]),
                    weight=ft.FontWeight.W_600)),
            ]) for f in r.filas_tabla()],
        )

        bloques_flexion = self._resultados_flexion() if r.flexion else []
        self.panel_resultados.controls = [
            *bloques_flexion[:2], banner, indicadores, *bloques_flexion[2:], figuras,
            es.tarjeta(es.titulo("Tabla comparativa", ft.Icons.TABLE_CHART,
                                 "Variación = (Modificada − Ideal) / Ideal × 100"),
                       ft.Row([tabla], scroll=ft.ScrollMode.AUTO)),
        ]
        self.page.update()

    def _resultados_flexion(self):
        """Aviso, indicadores, gráfica y tabla del chequeo a flexión."""
        f = self.resultado.flexion
        mod = f.modificada
        verde, rojo = es.SEVERIDAD["VERDE"], es.SEVERIDAD["ROJO"]
        color, fondo, icono = verde if mod.cumple else rojo

        if f.alfa_falla == 0.0:
            vida_txt = "No cumple ni con la sección de diseño"
        elif f.tiempo_falla is not None:
            restante = f.tiempo_falla - f.edad_anios
            vida_txt = (f"Deja de cumplir a los {f.tiempo_falla:.1f} años "
                        f"({'hace' if restante < 0 else 'en'} {abs(restante):.1f} años)")
        elif f.alfa_falla is not None:
            vida_txt = f"Deja de cumplir con un nivel de daño α = {f.alfa_falla:.2f}"
        else:
            vida_txt = "Sigue cumpliendo en todo el rango proyectado"

        banner = ft.Container(
            padding=18, border_radius=14, bgcolor=fondo, border=es.borde(1, color),
            content=ft.Row(spacing=16, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                           controls=[
                ft.Icon(ft.Icons.STRAIGHTEN, color=color, size=44),
                ft.Column(spacing=2, expand=True, controls=[
                    ft.Text("Chequeo a flexión NSR-10 · sección inspeccionada", size=13,
                            color=color, weight=ft.FontWeight.W_600),
                    ft.Text(f"φMn = {mod.phi_mn:,.1f} kN·m   vs   Mu = {mod.mu:,.1f} kN·m",
                            size=20, weight=ft.FontWeight.BOLD, color=es.TEXTO),
                    ft.Text(f"Mu / φMn = {mod.relacion:.2f}  ·  {vida_txt}", size=13,
                            color=es.TEXTO_SUAVE),
                ]),
                es.chip("CUMPLE" if mod.cumple else "NO CUMPLE", es.TARJETA, color),
            ]),
        )

        def color_rel(r):
            return verde[0] if r.cumple else rojo[0]

        indicadores = ft.ResponsiveRow(spacing=12, run_spacing=12, controls=[
            es.indicador("φMn sección ideal", f"{f.ideal.phi_mn:,.0f}", "kN·m",
                         color_rel(f.ideal), {"xs": 6, "md": 3},
                         detalle=f"Mu/φMn = {f.ideal.relacion:.2f}"),
            es.indicador("φMn sección inspeccionada", f"{mod.phi_mn:,.0f}", "kN·m",
                         color_rel(mod), {"xs": 6, "md": 3},
                         detalle=f"Pierde {f.perdida_phi_mn:.1f} %"),
            es.indicador("Momento último Mu", f"{mod.mu:,.0f}", "kN·m", es.PRIMARIO,
                         {"xs": 6, "md": 3}, detalle=f"wu = {mod.wu:.1f} kN/m"),
            es.indicador("Acero inspeccionado", f"{mod.as_total_mm2:,.0f}", "mm²", es.PRIMARIO,
                         {"xs": 6, "md": 3},
                         detalle=f"−{f.datos.perdida_acero:g} % por corrosión"),
        ])

        figura = es.tarjeta(
            es.titulo("Flexión de la sección inspeccionada", ft.Icons.STRAIGHTEN,
                      f"c = {mod.c * 100:.1f} cm · a = {mod.a * 100:.1f} cm · "
                      f"εt = {mod.eps_t * 1000:.1f} ‰ · φ = {mod.phi:.2f}"),
            imagen_png(graficas.figura_a_png(graficas.figura_flexion(mod, oscuro=True)),
                       fit=AJUSTE_CONTENER),
            padding=14)

        def fila(nombre, unidad, vi, vm, formato="{:,.2f}"):
            return ft.DataRow(cells=[ft.DataCell(ft.Text(nombre)), ft.DataCell(ft.Text(unidad)),
                                     ft.DataCell(ft.Text(formato.format(vi))),
                                     ft.DataCell(ft.Text(formato.format(vm)))])

        i = f.ideal
        tabla = ft.DataTable(
            heading_row_color=es.PRIMARIO_CLARO, column_spacing=28,
            columns=[ft.DataColumn(ft.Text(t, weight=ft.FontWeight.W_600)) for t in
                     ("Resultado", "Unidad", "Ideal", "Inspeccionada")],
            rows=[
                fila("Área de acero As", "mm²", i.as_total_mm2, mod.as_total_mm2, "{:,.0f}"),
                fila("Eje neutro c", "cm", i.c * 100, mod.c * 100),
                fila("Bloque de Whitney a = β1·c", "cm", i.a * 100, mod.a * 100),
                fila("Deformación del acero extremo εt", "‰", i.eps_t * 1000, mod.eps_t * 1000),
                fila("Factor φ", "-", i.phi, mod.phi),
                fila("Resistencia nominal Mn", "kN·m", i.mn, mod.mn, "{:,.1f}"),
                fila("Resistencia de diseño φMn", "kN·m", i.phi_mn, mod.phi_mn, "{:,.1f}"),
                fila("Momento de agrietamiento Mcr", "kN·m", i.mcr, mod.mcr, "{:,.1f}"),
                fila("Peso propio", "kN/m", i.peso_propio, mod.peso_propio),
                fila("Momento último Mu", "kN·m", i.mu, mod.mu, "{:,.1f}"),
                fila("Mu / φMn", "-", i.relacion, mod.relacion),
            ],
        )
        avisos = []
        if not mod.ductil:
            avisos.append("εt < 0.004: la sección no es dúctil (NSR-10 C.10.3.5).")
        if not mod.cumple_as_min:
            avisos.append(f"As < As,mín = {mod.as_min_mm2:,.0f} mm² (NSR-10 C.10.5.1).")
        detalle = es.tarjeta(
            es.titulo("Resultados a flexión", ft.Icons.TABLE_CHART,
                      f"f'c = {f.datos.fc:g} MPa · fy = {f.datos.fy:g} MPa · β1 = {i.beta1:.3f} · "
                      f"L = {f.datos.luz:g} m"),
            ft.Row([tabla], scroll=ft.ScrollMode.AUTO),
            *[ft.Text(a, color=es.SEVERIDAD["NARANJA"][0], size=12.5) for a in avisos])
        return [banner, indicadores, figura, detalle]

    def _texto_proyeccion(self):
        proy = self.resultado.proyeccion
        partes = []
        for umbral in (modelo.UMBRAL_PREVENTIVO, modelo.UMBRAL_INTERVENCION):
            a, t = proy.alfa_umbral.get(umbral), proy.tiempo_umbral(umbral)
            if a is None:
                partes.append(f"{umbral:.0f} %: no se alcanza")
            elif t is not None:
                partes.append(f"{umbral:.0f} % a los {t:.1f} años")
            else:
                partes.append(f"{umbral:.0f} % con α = {a:.2f}")
        return "Umbrales (scipy brentq): " + "  ·  ".join(partes)
