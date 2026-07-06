"""Interfaz de línea de comandos del Sistema de Cobranza Escolar.

Ejemplos
--------
    python main.py "Cuentas por Cobrar.csv"
    python main.py datos.xlsx --fecha-corte 2026-07-03 --salida reporte.xlsx
    python main.py datos.xlsx --color Rojo
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from cobranza import (
    analizar_cartera,
    cargar_config,
    cargar_movimientos,
    exportar_reporte,
)
from cobranza.analisis import resumen_indicadores


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Analiza la cartera escolar y genera el reporte de cobranza."
    )
    p.add_argument("archivo", help="Ruta del archivo .csv o .xlsx de Cuentas por Cobrar")
    p.add_argument(
        "--fecha-corte",
        default=None,
        help="Fecha de referencia (YYYY-MM-DD). Por defecto: hoy.",
    )
    p.add_argument(
        "--salida",
        default=None,
        help="Ruta del reporte Excel a generar. Por defecto: reporte_cobranza_<fecha>.xlsx",
    )
    p.add_argument(
        "--color",
        choices=["Verde", "Amarillo", "Naranja", "Rojo"],
        default=None,
        help="Muestra en consola solo los alumnos de ese semáforo.",
    )
    p.add_argument("--config", default=None, help="Ruta a config.yaml")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    cfg = cargar_config(args.config)

    fecha_corte = args.fecha_corte or date.today().isoformat()

    print(f"Leyendo: {args.archivo}")
    df = cargar_movimientos(args.archivo)
    print(f"Movimientos cargados: {len(df):,}")

    estado = analizar_cartera(df, fecha_corte=fecha_corte, cfg=cfg)
    ind = resumen_indicadores(estado, fecha_corte)

    print("\n" + "=" * 60)
    print(f"  ESTADO DE CARTERA  |  Corte: {ind.get('fecha_corte')}")
    print("=" * 60)
    print(f"  Total alumnos      : {ind.get('total_alumnos', 0)}")
    print(f"  Con adeudo vencido : {ind.get('alumnos_con_adeudo_vencido', 0)} ({ind.get('porcentaje_adeudo_vencido', 0)}%)")
    print(f"  Saldo pendiente    : ${ind.get('saldo_total', 0):,.2f}")
    print("-" * 60)
    for c in ["Verde", "Amarillo", "Naranja", "Rojo"]:
        n = ind.get("conteo", {}).get(c, 0)
        pct = ind.get("porcentaje", {}).get(c, 0)
        saldo = ind.get("saldo_por_color", {}).get(c, 0)
        print(f"  {c:<9}: {n:>4} alumnos  ({pct:>5}%)   ${saldo:,.2f}")
    print("=" * 60)

    if args.color:
        sub = estado[estado["Semáforo"] == args.color]
        print(f"\nAlumnos en semáforo {args.color} ({len(sub)}):\n")
        cols = ["Matrícula", "Alumno", "Nivel", "Grado", "Saldo", "Días Atraso", "Responsable"]
        cols = [c for c in cols if c in sub.columns]
        if sub.empty:
            print("  (ninguno)")
        else:
            print(sub[cols].to_string(index=False))

    salida = args.salida or f"reporte_cobranza_{ind.get('fecha_corte')}.xlsx"
    ruta = exportar_reporte(estado, salida, fecha_corte=fecha_corte)
    print(f"\nReporte generado: {Path(ruta).resolve()}")


if __name__ == "__main__":
    main()
