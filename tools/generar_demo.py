"""Genera datos y coeficientes para la edición web a partir del proyecto Python.

Usar el intérprete del entorno virtual del proyecto y ejecutar:
    python tools/generar_demo.py /ruta/al/proyecto-retail-sales-forecast
"""

import argparse
import json
import sys
from contextlib import closing
from datetime import date
from pathlib import Path


def generar(ruta: Path) -> None:
    sys.path.insert(0, str(ruta.resolve()))
    import app

    firma = app.BD.stat().st_mtime_ns
    cobertura, sucursales, productos = app.catalogo(firma)
    inicio = date.fromisoformat(cobertura["inicio"])

    with closing(app.conexion()) as con:
        filas = con.execute(
            """
            SELECT CAST(julianday(fecha) - julianday(?) AS INTEGER),
                   sucursal_id, producto_id, unidades, precio_lista_centavos,
                   descuento_pct, precio_neto_centavos, costo_unitario_centavos
            FROM v_ventas_detalle
            ORDER BY fecha, sucursal_id, producto_id
            """,
            (inicio.isoformat(),),
        ).fetchall()
        pares = con.execute("SELECT DISTINCT sucursal_id, producto_id FROM ventas ORDER BY 1, 2")
        catalogo = {}
        for sucursal, producto in pares:
            precios = app.consultar(con, "precios_escenario", {
                "sucursal_id": sucursal, "producto_id": producto,
            }).iloc[0]
            catalogo[f"{sucursal}-{producto}"] = [
                int(precios[clave]) for clave in ("minimo", "maximo", "reciente", "referencia")
            ]

    modelo = app.entrenar(firma)
    preparador, estimador = modelo.estimador
    encoder = preparador.named_transformers_["categorias"]
    nombres = encoder.get_feature_names_out(app.CATEGORICAS)
    cantidad = len(nombres)
    coeficientes = dict(zip(nombres.tolist(), estimador.coef_[:cantidad].tolist(), strict=True))

    datos = {
        "inicio": inicio.isoformat(),
        "fin": cobertura["fin"],
        "sucursales": list(sucursales[["sucursal_id", "nombre"]].itertuples(index=False, name=None)),
        "productos": list(productos[["producto_id", "nombre", "categoria"]].itertuples(index=False, name=None)),
        "ventas": filas,
        "precios": catalogo,
        "modelo": {
            "intercepto": float(estimador.intercept_),
            "categorias": coeficientes,
            "numericas": estimador.coef_[cantidad:].tolist(),
            "metricas": modelo.indicadores.to_dict(orient="records"),
        },
    }
    salida = Path(__file__).resolve().parents[1] / "datos.json"
    salida.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(filas):,} observaciones exportadas a {salida.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proyecto", type=Path)
    generar(parser.parse_args().proyecto)
