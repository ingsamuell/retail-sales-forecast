# Retail Sales Forecast

Monitor de ventas y simulador de demanda para una cadena de supermercados ficticia. La aplicación permite revisar qué se vende y con qué margen, y estimar las unidades diarias para una decisión de precio o promoción.

## Qué puedes explorar

- **Monitor de ventas.** Filtra por fechas, sucursal y categoría. Consulta ingresos netos, unidades vendidas, utilidad y margen bruto. Cuando existe cobertura completa, los KPI se comparan con el período inmediatamente anterior de igual duración.
- **Simulador de demanda.** Elige una sucursal, un producto y una fecha dentro de los 90 días posteriores al historial. Ajusta el precio de lista dentro de su rango observado y el descuento entre 0 % y 30 %. El resultado compara las unidades estimadas con y sin descuento al mismo precio de lista.
- **Exportación a Excel.** Descarga un `.xlsx` con las hojas **Resumen** y **Ventas filtradas**. El resumen incluye filtros, KPI y resultados por categoría. Los importes, las fechas y los porcentajes se pueden usar en fórmulas de Excel. El libro se prepara bajo demanda y sus hojas se escriben por filas para limitar el consumo de memoria.

## Hallazgos de negocio

Los siguientes resultados provienen de los datos sintéticos incluidos en el repositorio. Corresponden a años calendario completos.

| Indicador | 2024 | 2025 |
| --- | ---: | ---: |
| Ingresos netos | USD 1.992.386,36 | USD 2.048.248,69 |
| Unidades vendidas | 832.084 | 854.451 |
| Utilidad bruta | USD 654.969,41 | USD 642.039,66 |
| Margen bruto | 32,87 % | 31,35 % |

- **El volumen creció y la rentabilidad se redujo.** En 2025 los ingresos subieron 2,8 % y las unidades 2,7 %. La utilidad bruta bajó 2,0 % y el margen cedió 1,53 puntos porcentuales, usando las cifras sin redondear.
- **Refrigerados lideró en ingresos y Bebidas obtuvo el mayor margen.** Refrigerados generó USD 502.441,51 con un margen de 27,66 %. Bebidas generó USD 386.210,31 con un margen de 35,93 %. Mirar ambos indicadores permite distinguir las categorías que impulsan ventas de las que retienen más utilidad por dólar vendido.
- **Chacao lideró entre las sucursales.** Facturó USD 486.789,01 en 2025, el 23,8 % del total. Diciembre fue el mes con más ingresos para la cadena, con USD 191.653,04. En todo el historial, el sábado promedió 29,43 unidades por sucursal y producto, frente a 18,65 el lunes.

## Datos, SQL y métricas

El generador usa NumPy con semilla 42 y crea **73.100 observaciones** entre 2024-01-01 y 2025-12-31. Cada observación representa un día, una sucursal y un producto, e incluye los días con cero unidades vendidas. Los datos incorporan diferencias entre sucursales, estacionalidad semanal, quincenas, promociones y costos variables. La moneda de la demo es USD.

| Tabla | Grano | Campos principales |
| --- | --- | --- |
| `sucursales` | 5 sucursales | ID, nombre, ciudad, formato |
| `productos` | 20 productos en 5 categorías | ID, nombre, categoría, precio de referencia |
| `ventas` | Día × sucursal × producto | Fecha, claves foráneas, unidades, precio de lista, descuento, costo unitario |

La clave primaria compuesta evita duplicar una combinación diaria. La vista SQL `v_ventas_detalle` une las tres tablas con `JOIN`. El [archivo de consultas](sql/consultas_kpi.sql) contiene el SQL ejecutado por Streamlit, con parámetros enlazados, agregaciones y `GROUP BY`. La aplicación abre SQLite en modo de solo lectura.

- **Ingresos netos** = suma de unidades × precio después de descuento. El precio neto unitario se redondea al centavo antes de multiplicar.
- **Utilidad bruta** = ingresos netos menos costo de venta. El costo de venta es la suma de unidades × costo unitario.
- **Margen bruto** = utilidad bruta ÷ ingresos netos. Si los ingresos son cero, el margen queda sin valor.

El CSV es un respaldo de la vista SQL con encabezados y codificación UTF-8. Los campos con sufijo `_centavos` preservan los importes originales como enteros. La aplicación analiza los resultados con Pandas y visualiza la serie diaria y el ranking con Matplotlib y Seaborn.

## Modelo y evaluación

El simulador usa una regresión de Poisson regularizada de Scikit-learn para estimar el número esperado de unidades vendidas. El modelo combina sucursal y producto, categoría y mes, día de la semana, quincenas, fiestas, tendencia, precio relativo y descuento. La codificación de categorías se ajusta dentro de la canalización de entrenamiento.

La evaluación reserva las **5.600 observaciones del 6 de noviembre al 31 de diciembre de 2025**. La referencia predice la mediana de unidades para la misma sucursal, producto y día de la semana, calculada solo con el conjunto de entrenamiento. Tras evaluar, el simulador ajusta el modelo con todo el historial y lo reutiliza en memoria.

| Método | MAE | WAPE |
| --- | ---: | ---: |
| Regresión de Poisson | 4,39 unidades | 17,72 % |
| Mediana histórica | 6,05 unidades | 24,43 % |

**MAE** es el error absoluto medio en unidades por observación. **WAPE** divide la suma de errores absolutos por la suma de unidades observadas. La evaluación mide desempeño sobre ventas sintéticas. El modelo estima ventas bajo los escenarios definidos y sus diferencias reflejan las relaciones aprendidas del generador.

## Ejecutar en Linux

Ejecuta estos comandos desde la raíz del proyecto con Python 3.12 y soporte para `venv`.

```bash
python3.12 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

La base y el CSV ya están generados. Puedes reconstruir ambos con la misma semilla usando el generador.

```bash
python data/generar_datos.py
```

## Desplegar en Streamlit Community Cloud

1. Publica el repositorio en GitHub con `requirements.txt`, `data/retail.db` y `sql/consultas_kpi.sql`.
2. En Streamlit Community Cloud, crea una aplicación y selecciona el repositorio y su rama.
3. Indica `app.py` como archivo principal y elige Python 3.12 en los ajustes avanzados. Despliega desde la interfaz. [Guía oficial de despliegue](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)

## Estructura

```text
retail-sales-forecast/
├── data/
│   ├── generar_datos.py
│   ├── retail.db
│   └── ventas_supermercado.csv
├── sql/
│   └── consultas_kpi.sql
├── app.py
├── requirements.txt
├── .gitignore
└── README.md
```
