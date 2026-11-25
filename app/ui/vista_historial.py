"""Vista «Historial»: listar, buscar, comparar, reabrir y eliminar cálculos."""

import flet as ft

from app import db
from app.ui import estilos as es
from app.ui.compat import abrir, avisar, boton, cerrar
from app.ui.utilidades import generar_y_abrir_memoria


class VistaHistorial:
    def __init__(self, page, conexion, al_abrir, autores=lambda: ""):
        self.page = page
        self.conexion = conexion
        self.al_abrir = al_abrir          # callback(calculo) para reabrir en «Cálculo»
        self.autores = autores
        self.txt_buscar = ft.TextField(
            hint_text="Buscar por proyecto, cálculo o severidad (VERDE, NARANJA, ROJO)",
            prefix_icon=ft.Icons.SEARCH, dense=True, border_radius=24, expand=True,
            on_submit=lambda e: self.refrescar())
        self.resumen = ft.ResponsiveRow(spacing=12, run_spacing=12)
        self.contenido = ft.Column(spacing=0)
        self.control = ft.Column(
            expand=True, scroll=ft.ScrollMode.AUTO, spacing=16,
            controls=[
                es.tarjeta(
                    es.titulo("Historial y comparación", ft.Icons.HISTORY,
                              "Cálculos guardados en la base de datos SQLite. Reabra, genere "
                              "la memoria o elimine cada cálculo."),
                    ft.Row([self.txt_buscar,
                            boton("Buscar", lambda e: self.refrescar(), ft.Icons.SEARCH),
                            boton("Ver todos", self._on_ver_todos, ft.Icons.LIST, "text")],
                           wrap=False),
                ),
                self.resumen,
                self.contenido,
            ],
        )

    def _on_ver_todos(self, e):
        self.txt_buscar.value = ""
        self.refrescar()

    def refrescar(self, actualizar=True):
        calculos = db.listar_calculos(self.conexion, self.txt_buscar.value or "")
        conteo = {s: sum(c["severidad"] == s for c in calculos) for s in es.SEVERIDAD}
        self.resumen.controls = [
            es.indicador("Cálculos encontrados", str(len(calculos)), "", es.PRIMARIO,
                         {"xs": 6, "md": 3}),
        ] + [
            es.indicador(f"Severidad {s.lower()}", str(n), "", es.SEVERIDAD[s][0],
                         {"xs": 6, "md": 3})
            for s, n in conteo.items()
        ]
        if not calculos:
            self.contenido.controls = [es.estado_vacio(
                ft.Icons.INBOX, "No hay cálculos para mostrar",
                "Guarde un cálculo desde la vista «Cálculo» o cambie el texto de búsqueda.")]
        else:
            tabla = ft.DataTable(
                heading_row_color=es.PRIMARIO_CLARO, column_spacing=22,
                columns=[ft.DataColumn(ft.Text(t, weight=ft.FontWeight.W_600)) for t in (
                    "Id", "Proyecto", "Cálculo", "Sección", "A ideal (m²)", "A mod (m²)",
                    "Zx ideal (m³)", "Zx mod (m³)", "Pérdida Zx (%)", "Severidad",
                    "φMn mod (kN·m)", "Mu (kN·m)", "Flexión", "Estación crítica",
                    "Fecha", "Acciones")],
                rows=[self._fila(c) for c in calculos],
            )
            self.contenido.controls = [es.tarjeta(
                ft.Row([tabla], scroll=ft.ScrollMode.AUTO), padding=8)]
        if actualizar:
            self.page.update()

    def _fila(self, c):
        color, fondo, _ = es.SEVERIDAD[c["severidad"]]
        acciones = ft.Row(spacing=0, controls=[
            ft.IconButton(icon=ft.Icons.OPEN_IN_NEW, tooltip="Reabrir en Cálculo",
                          icon_color=es.PRIMARIO,
                          on_click=lambda e, i=c["id"]: self._abrir(i)),
            ft.IconButton(icon=ft.Icons.DESCRIPTION, tooltip="Generar memoria .docx",
                          icon_color=es.PRIMARIO,
                          on_click=lambda e, i=c["id"]: generar_y_abrir_memoria(
                              self.page, self.conexion, i, self.autores())),
            ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, tooltip="Eliminar",
                          icon_color=es.SEVERIDAD["ROJO"][0],
                          on_click=lambda e, calc=c: self._confirmar_eliminar(calc)),
        ])
        textos = [str(c["id"]), c["proyecto"], c["nombre"],
                  "Bulb-Tee" if c["tipo_seccion"] == "bulb_tee" else "Rectangular",
                  f"{c['area_ideal']:.4f}", f"{c['area_mod']:.4f}",
                  f"{c['zx_ideal']:.4f}", f"{c['zx_mod']:.4f}"]
        celdas = [ft.DataCell(ft.Text(t)) for t in textos]
        celdas += [
            ft.DataCell(ft.Text(f"{c['perdida_zx']:.2f}", color=color,
                                weight=ft.FontWeight.W_600)),
            ft.DataCell(es.chip(c["severidad"], color, fondo)),
            *self._celdas_flexion(c),
            self._celda_estaciones(c),
            ft.DataCell(ft.Text(c["creado"].replace("T", " ")[:16], color=es.TEXTO_SUAVE)),
            ft.DataCell(acciones),
        ]
        return ft.DataRow(cells=celdas)

    @staticmethod
    def _celdas_flexion(c):
        """φMn, Mu y CUMPLE / NO CUMPLE, o guiones si el cálculo no evaluó flexión."""
        if c.get("phi_mn_mod") is None:
            return [ft.DataCell(ft.Text("—", color=es.TEXTO_SUAVE)) for _ in range(3)]
        cumple = bool(c["cumple_flexion"])
        color, fondo, _ = es.SEVERIDAD["VERDE" if cumple else "ROJO"]
        return [ft.DataCell(ft.Text(f"{c['phi_mn_mod']:,.0f}")),
                ft.DataCell(ft.Text(f"{c['mu']:,.0f}")),
                ft.DataCell(es.chip("CUMPLE" if cumple else "NO CUMPLE", color, fondo))]

    @staticmethod
    def _celda_estaciones(c):
        """x crítico y demanda/resistencia, o un guion si no se revisó por estaciones."""
        if c.get("x_critico") is None:
            return ft.DataCell(ft.Text("—", color=es.TEXTO_SUAVE))
        color, fondo, _ = es.SEVERIDAD["VERDE" if c["cumple_estaciones"] else "ROJO"]
        return ft.DataCell(es.chip(f"x = {c['x_critico']:g} m · {c['relacion_max']:.2f}",
                                   color, fondo))

    def _abrir(self, calculo_id):
        calculo = db.obtener_calculo(self.conexion, calculo_id)
        if calculo is None:
            avisar(self.page, "El cálculo ya no existe.", error=True)
            self.refrescar()
            return
        self.al_abrir(calculo)

    def _confirmar_eliminar(self, calculo):
        def eliminar(e):
            cerrar(self.page, dialogo)
            db.eliminar_calculo(self.conexion, calculo["id"])
            self.refrescar()
            avisar(self.page, f"Cálculo «{calculo['nombre']}» eliminado.")

        dialogo = ft.AlertDialog(
            modal=True,
            icon=ft.Icon(ft.Icons.DELETE_OUTLINE, color=es.SEVERIDAD["ROJO"][0]),
            title=ft.Text("¿Eliminar cálculo?"),
            content=ft.Text(f"Se eliminará «{calculo['nombre']}» del proyecto "
                            f"«{calculo['proyecto']}». Esta acción no se puede deshacer."),
            actions=[boton("Cancelar", lambda e: cerrar(self.page, dialogo), tipo="text"),
                     boton("Eliminar", eliminar, ft.Icons.DELETE)],
        )
        abrir(self.page, dialogo)
