# Retail Sales Forecast

Monitor de ventas y simulador de demanda para una cadena de supermercados ficticia. Analiza **73.100 registros sintéticos** de 5 sucursales y 20 productos durante 2024–2025.

[Ver el portafolio](https://ingsamuell.github.io/retail-sales-forecast/)

## Qué puedes probar

- **Monitor.** Filtra ventas por fecha, sucursal y categoría. Compara ingresos netos, unidades y margen bruto.
- **Simulador.** Explora cómo cambia la demanda estimada al ajustar el precio o el descuento de un producto.
- **Excel.** Exporta el detalle filtrado y un resumen de indicadores.

**Hallazgo.** En 2025, los ingresos subieron **2,8 %** y el margen bruto cayó **1,53 puntos porcentuales**.

**Modelo.** La regresión de Poisson obtuvo **17,72 % de WAPE** frente a **24,43 %** de la mediana histórica en las últimas ocho semanas del conjunto sintético.

**Stack.** Python, SQLite, Pandas, NumPy, Matplotlib, Seaborn, scikit-learn, Streamlit y openpyxl.

<details>
<summary>Ejecutar en Linux con Python 3.12</summary>

```bash
git clone https://github.com/ingsamuell/retail-sales-forecast.git
cd retail-sales-forecast
python3.12 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

El repositorio incluye SQLite y el CSV. El generador `data/generar_datos.py` permite reconstruirlos con la misma semilla.

</details>
