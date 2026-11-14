"""Vista «Historial»: listar, buscar, comparar, reabrir y eliminar cálculos."""

import flet as ft

from app import db
from app.ui.compat import abrir, avisar, boton, cerrar
from app.ui.utilidades import COLOR_SEVERIDAD, generar_y_abrir_memoria


class VistaHistorial:
    def __init__(self, page, conexion, al_abrir, autores=lambda: ""):
        self.page = page
        self.conexion = conexion
        self.al_abrir = al_abrir          # callback(calculo) para reabrir en «Cálculo»
        self.autores = autores
        self.txt_buscar = ft.TextField(label="Buscar por proyecto, cálculo o severidad",
                                       width=380, on_submit=lambda e: self.refrescar())
        self.tabla = ft.Column()
        self.lbl_total = ft.Text()
        self.control = ft.Column(
            expand=True, scroll=ft.ScrollMode.AUTO, spacing=12,
            controls=[
                ft.Text("Historial y comparación de cálculos", size=20,
                        weight=ft.FontWeight.BOLD),
                ft.Row(wrap=True, controls=[
                    self.txt_buscar,
                    boton("Buscar", lambda e: self.refrescar(), ft.Icons.SEARCH),
                    boton("Ver todos", self._on_ver_todos, ft.Icons.LIST, "text"),
                ]),
                self.lbl_total,
                self.tabla,
            ],
        )

    def _on_ver_todos(self, e):
        self.txt_buscar.value = ""
        self.refrescar()

    def refrescar(self, actualizar=True):
        calculos = db.listar_calculos(self.conexion, self.txt_buscar.value or "")
        self.lbl_total.value = f"{len(calculos)} cálculo(s) encontrados."
        if not calculos:
            self.tabla.controls = [ft.Text("No hay cálculos guardados todavía. Use la vista "
                                           "Cálculo y presione «Guardar en historial».",
                                           italic=True)]
        else:
            self.tabla.controls = [ft.DataTable(
                columns=[ft.DataColumn(ft.Text(t)) for t in (
                    "Id", "Proyecto", "Cálculo", "Sección", "A ideal (m²)", "A mod (m²)",
                    "Zx ideal (m³)", "Zx mod (m³)", "Pérdida Zx (%)", "Severidad",
                    "Fecha", "Acciones")],
                rows=[self._fila(c) for c in calculos],
            )]
        if actualizar:
            self.page.update()

    def _fila(self, c):
        severidad = ft.Container(
            bgcolor=COLOR_SEVERIDAD[c["severidad"]], border_radius=6,
            padding=4,
            content=ft.Text(c["severidad"], color=ft.Colors.WHITE, size=12))
        acciones = ft.Row(spacing=0, controls=[
            ft.IconButton(icon=ft.Icons.FOLDER_OPEN, tooltip="Reabrir en Cálculo",
                          on_click=lambda e, i=c["id"]: self._abrir(i)),
            ft.IconButton(icon=ft.Icons.DESCRIPTION, tooltip="Generar memoria .docx",
                          on_click=lambda e, i=c["id"]: generar_y_abrir_memoria(
                              self.page, self.conexion, i, self.autores())),
            ft.IconButton(icon=ft.Icons.DELETE, tooltip="Eliminar", icon_color=ft.Colors.RED_700,
                          on_click=lambda e, calc=c: self._confirmar_eliminar(calc)),
        ])
        textos = [str(c["id"]), c["proyecto"], c["nombre"],
                  "Bulb-Tee" if c["tipo_seccion"] == "bulb_tee" else "Rectangular",
                  f"{c['area_ideal']:.4f}", f"{c['area_mod']:.4f}",
                  f"{c['zx_ideal']:.4f}", f"{c['zx_mod']:.4f}", f"{c['perdida_zx']:.2f}"]
        celdas = [ft.DataCell(ft.Text(t)) for t in textos]
        celdas += [ft.DataCell(severidad), ft.DataCell(ft.Text(c["creado"].replace("T", " "))),
                   ft.DataCell(acciones)]
        return ft.DataRow(cells=celdas)

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
            title=ft.Text("Eliminar cálculo"),
            content=ft.Text(f"¿Seguro que desea eliminar «{calculo['nombre']}» del proyecto "
                            f"«{calculo['proyecto']}»? Esta acción no se puede deshacer."),
            actions=[boton("Cancelar", lambda e: cerrar(self.page, dialogo), tipo="text"),
                     boton("Eliminar", eliminar, ft.Icons.DELETE)],
        )
        abrir(self.page, dialogo)
