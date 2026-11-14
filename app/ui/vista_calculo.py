"""Vista «Cálculo»: formulario de entrada, validación, resultados y gráficas.

Diseño responsive: en pantallas anchas el formulario queda a la izquierda y los
resultados a la derecha; en pantallas angostas se apilan uno debajo del otro.
"""

import flet as ft

from app import db, graficas, modelo
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
        self.txt_proyecto.value = self.txt_proyecto.value or "Puente ejemplo"
        self.txt_nombre.value = self.txt_nombre.value or "Viga exterior - inspección"
        self.calculo_id = None
        self.calcular()

    def _on_limpiar(self, e):
        self._crear_campos()
        for campo in (self.txt_edad, self.txt_nombre):
            campo.value, campo.error_text = "", None
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

        self.panel_resultados.controls = [
            banner, indicadores, figuras,
            es.tarjeta(es.titulo("Tabla comparativa", ft.Icons.TABLE_CHART,
                                 "Variación = (Modificada − Ideal) / Ideal × 100"),
                       ft.Row([tabla], scroll=ft.ScrollMode.AUTO)),
        ]
        self.page.update()

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
