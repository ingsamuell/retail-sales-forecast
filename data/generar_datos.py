"""Genera un panel diario reproducible de ventas minoristas sintéticas."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np


INICIO = date(2024, 1, 1)
FIN = date(2025, 12, 31)
SEMILLA = 42

# Identificador, nombre, ciudad, formato y factor de afluencia.
SUCURSALES = (
    (1, "Chacao", "Caracas", "Urbano", 1.23),
    (2, "La Trinidad", "Caracas", "Urbano", 0.94),
    (3, "San Diego", "Valencia", "Supermercado", 1.12),
    (4, "Barquisimeto Este", "Barquisimeto", "Supermercado", 0.86),
    (5, "Maracaibo Norte", "Maracaibo", "Supermercado", 1.04),
)

# SKU, nombre, categoría, precio y costo de referencia en centavos, demanda diaria.
PRODUCTOS = (
    (1, "Arroz blanco 1 kg", "Despensa", 215, 139, 24),
    (2, "Pasta corta 500 g", "Despensa", 178, 116, 20),
    (3, "Aceite vegetal 1 L", "Despensa", 398, 284, 16),
    (4, "Café molido 250 g", "Despensa", 545, 352, 12),
    (5, "Cambur 1 kg", "Frescos", 179, 104, 28),
    (6, "Tomate 500 g", "Frescos", 163, 92, 21),
    (7, "Aguacate 1 kg", "Frescos", 375, 242, 11),
    (8, "Naranja 1 kg", "Frescos", 199, 123, 16),
    (9, "Agua mineral 1,5 L", "Bebidas", 95, 53, 38),
    (10, "Jugo de naranja 1 L", "Bebidas", 329, 198, 16),
    (11, "Té frío 500 ml", "Bebidas", 139, 83, 24),
    (12, "Refresco cola 2 L", "Bebidas", 259, 156, 20),
    (13, "Leche entera 1 L", "Refrigerados", 229, 158, 35),
    (14, "Yogur natural 180 g", "Refrigerados", 146, 89, 23),
    (15, "Queso blanco 400 g", "Refrigerados", 445, 302, 16),
    (16, "Mantequilla 200 g", "Refrigerados", 390, 262, 10),
    (17, "Detergente en polvo 1 kg", "Hogar", 499, 321, 9),
    (18, "Papel higiénico 4 rollos", "Hogar", 389, 248, 14),
    (19, "Lavaplatos líquido 500 ml", "Hogar", 268, 161, 8),
    (20, "Limpiador multiuso 1 L", "Hogar", 310, 188, 6),
)

ESQUEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE sucursales (
    sucursal_id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,
    ciudad TEXT NOT NULL,
    formato TEXT NOT NULL
);

CREATE TABLE productos (
    producto_id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,
    categoria TEXT NOT NULL,
    precio_referencia_centavos INTEGER NOT NULL CHECK (
        typeof(precio_referencia_centavos) = 'integer' AND precio_referencia_centavos > 0
    )
);

CREATE TABLE ventas (
    fecha TEXT NOT NULL,
    sucursal_id INTEGER NOT NULL REFERENCES sucursales(sucursal_id),
    producto_id INTEGER NOT NULL REFERENCES productos(producto_id),
    unidades INTEGER NOT NULL CHECK (typeof(unidades) = 'integer' AND unidades >= 0),
    precio_lista_centavos INTEGER NOT NULL CHECK (
        typeof(precio_lista_centavos) = 'integer' AND precio_lista_centavos > 0
    ),
    descuento_pct INTEGER NOT NULL CHECK (
        typeof(descuento_pct) = 'integer' AND descuento_pct BETWEEN 0 AND 30
    ),
    costo_unitario_centavos INTEGER NOT NULL CHECK (
        typeof(costo_unitario_centavos) = 'integer' AND costo_unitario_centavos > 0
    ),
    PRIMARY KEY (fecha, sucursal_id, producto_id)
) WITHOUT ROWID;

CREATE INDEX ventas_sucursal_fecha ON ventas (sucursal_id, fecha);
CREATE INDEX ventas_producto_fecha ON ventas (producto_id, fecha);
CREATE INDEX productos_categoria ON productos (categoria);

CREATE VIEW v_ventas_detalle AS
WITH precios AS (
    SELECT *, (precio_lista_centavos * (100 - descuento_pct) + 50) / 100
              AS precio_neto_centavos
    FROM ventas
)
SELECT v.fecha, v.sucursal_id, s.nombre AS sucursal, s.ciudad,
       v.producto_id, p.nombre AS producto, p.categoria, v.unidades,
       v.precio_lista_centavos, v.descuento_pct, v.precio_neto_centavos,
       v.costo_unitario_centavos,
       v.unidades * v.precio_neto_centavos AS ingresos_centavos,
       v.unidades * v.costo_unitario_centavos AS costo_venta_centavos,
       v.unidades * (v.precio_neto_centavos - v.costo_unitario_centavos)
           AS utilidad_centavos
FROM precios AS v
JOIN sucursales AS s ON s.sucursal_id = v.sucursal_id
JOIN productos AS p ON p.producto_id = v.producto_id;
"""


def simular_ventas() -> list[tuple[str, int, int, int, int, int, int]]:
    """Combina efectos de calendario, afluencia, precio y promociones semanales."""
    rng = np.random.default_rng(SEMILLA)
    dias = (FIN - INICIO).days + 1
    fechas = [INICIO + timedelta(days=i) for i in range(dias)]
    forma = (dias, len(SUCURSALES), len(PRODUCTOS))
    semana = (np.arange(dias) + INICIO.weekday()) // 7
    afluencia = np.array([fila[4] for fila in SUCURSALES])[None, :, None]
    precio_base = np.array([fila[3] for fila in PRODUCTOS])[None, None, :]
    costo_base = np.array([fila[4] for fila in PRODUCTOS])[None, None, :]
    consumo = np.array([fila[5] for fila in PRODUCTOS])[None, None, :]

    dias_semana = np.array([d.weekday() for d in fechas])
    factor_semana = np.array([0.83, 0.88, 0.90, 0.97, 1.14, 1.32, 1.18])
    quincena = np.array([1.13 if d.day in (1, 2, 14, 15, 16, 29, 30, 31) else 1
                        for d in fechas])
    fiestas = np.array([1.25 if d.month == 12 and d.day >= 15 else 1 for d in fechas])
    calendario = (factor_semana[dias_semana] * quincena * fiestas)[:, None, None]
    es_bebida = np.array([fila[2] == "Bebidas" for fila in PRODUCTOS])[None, None, :]
    meses = np.array([d.month for d in fechas])
    calor = 1 + 0.13 * (np.isin(meses, [3, 4, 5, 8, 9]))[:, None, None] * es_bebida
    tendencia = np.linspace(1.0, 1.063, dias)[:, None, None]

    promociones = rng.choice([0, 5, 10, 15, 20, 25, 30], size=(semana[-1] + 1, *forma[1:]),
                             p=[0.76, 0.03, 0.07, 0.05, 0.05, 0.025, 0.015])[semana]
    cambios_precio = rng.uniform(0.94, 1.08, size=(24, *forma[1:]))
    mes_idx = np.array([(d.year - INICIO.year) * 12 + d.month - 1 for d in fechas])
    precio_lista = np.rint(precio_base * cambios_precio[mes_idx]).astype(int)
    costo = np.rint(costo_base * np.linspace(1, 1.045, dias)[:, None, None])
    costo = np.broadcast_to(costo.astype(int), forma)
    efecto_precio = (precio_lista / precio_base) ** -1.25
    efecto_promo = 1 + 2.45 * promociones / 100
    afinidad = rng.uniform(0.8, 1.22, size=(1, *forma[1:]))
    variacion = rng.lognormal(mean=-0.5 * 0.11**2, sigma=0.11, size=forma)
    media = (consumo * afluencia * calendario * calor * tendencia * efecto_precio
             * efecto_promo * afinidad * variacion)
    unidades = rng.poisson(media)

    return [
        (fecha.isoformat(), sucursal[0], producto[0], int(unidades[d, s, p]),
         int(precio_lista[d, s, p]), int(promociones[d, s, p]), int(costo[d, s, p]))
        for d, fecha in enumerate(fechas)
        for s, sucursal in enumerate(SUCURSALES)
        for p, producto in enumerate(PRODUCTOS)
    ]


def generar(destino: Path) -> int:
    """Construye y verifica ambos archivos antes de reemplazar las copias previas."""
    destino.mkdir(parents=True, exist_ok=True)
    ventas = simular_ventas()
    with TemporaryDirectory(prefix=".generacion-", dir=destino) as temporal:
        bd = Path(temporal) / "retail.db"
        respaldo = Path(temporal) / "ventas_supermercado.csv"
        with closing(sqlite3.connect(bd)) as con:
            con.executescript(ESQUEMA)
            with con:
                con.executemany("INSERT INTO sucursales VALUES (?, ?, ?, ?)",
                                (fila[:4] for fila in SUCURSALES))
                con.executemany("INSERT INTO productos VALUES (?, ?, ?, ?)",
                                (fila[:4] for fila in PRODUCTOS))
                con.executemany("INSERT INTO ventas VALUES (?, ?, ?, ?, ?, ?, ?)", ventas)
            if con.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise RuntimeError("El panel diario contiene referencias inválidas.")

            filas = con.execute("""
                SELECT * FROM v_ventas_detalle ORDER BY fecha, sucursal_id, producto_id
            """)
            with respaldo.open("w", encoding="utf-8", newline="") as archivo:
                escritor = csv.writer(archivo)
                escritor.writerow(columna[0] for columna in filas.description)
                escritor.writerows(filas)

        respaldo.replace(destino / respaldo.name)
        bd.replace(destino / bd.name)
    return len(ventas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destino", type=Path, default=Path(__file__).resolve().parent,
                        help="Directorio de salida para SQLite y CSV.")
    args = parser.parse_args()
    total = generar(args.destino)
    print(f"{total:,} registros generados en {args.destino.resolve()}")


if __name__ == "__main__":
    main()
