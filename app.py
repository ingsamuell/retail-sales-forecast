"""Monitor de ventas y simulador de demanda de una cadena sintética."""

from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from html import escape
from io import BytesIO
from pathlib import Path
from threading import Lock

import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import seaborn as sns
import streamlit as st
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, MaxNLocator
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font, PatternFill
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder

RAIZ = Path(__file__).resolve().parent
BD = RAIZ / "data" / "retail.db"
SQL = RAIZ / "sql" / "consultas_kpi.sql"
LOG = logging.getLogger(__name__)

TINTA = "#122334"
TENUE = "#485c6e"
VERDE = "#087a64"
GRILLA = "#e3ebef"
MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
CATEGORICAS = ["sucursal_producto", "categoria_mes", "dia_semana"]
MONITOR = "Monitor de ventas"
SIMULADOR = "Simulador de demanda"
FORMATO_EXCEL_USD = '"USD" #,##0.00'
FORMATO_EXCEL_PCT = "0.0%"
RELLENO_EXCEL = PatternFill("solid", fgColor="143838")
FUENTE_EXCEL = Font(color="FFFFFF", bold=True)

COLUMNAS_DETALLE = {
    "fecha": "Fecha", "sucursal": "Sucursal", "ciudad": "Ciudad",
    "producto": "Producto", "categoria": "Categoría", "unidades": "Unidades",
    "descuento_pct": "Descuento", "precio_lista_centavos": "Precio de lista",
    "precio_neto_centavos": "Precio neto", "costo_unitario_centavos": "Costo unitario",
    "ingresos_centavos": "Ingresos netos", "costo_venta_centavos": "Costo de venta",
    "utilidad_centavos": "Utilidad bruta",
}

CSS = """
<style>
.stApp {
    --retail-fondo: #f2f6f7; --retail-panel: #fff; --retail-borde: #dbe5e8;
    --retail-texto: #122334; --retail-tenue: #485c6e;
    --retail-positivo: #075f4d; --retail-negativo: #a02f38;
    background: var(--retail-fondo); color: var(--retail-texto);
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stDecoration"], [data-testid="stAppDeployButton"] { visibility: hidden; }
[data-testid="stMainBlockContainer"] { max-width: 87rem; padding: 2.8rem 3rem 3rem; }
.stApp h1, .stApp h2, .stApp h3, .stApp p { letter-spacing: normal; }
.stApp h2, .stApp h3 { color: var(--retail-texto); }
.marca {
    display: flex; gap: .7rem; align-items: center; color: var(--retail-texto);
    font-weight: 750; font-size: .94rem; letter-spacing: .015em; margin: .15rem 0 .35rem;
}
.marca-icono {
    height: 2rem; width: 2rem; display: grid; place-items: center;
    border-radius: .55rem; background: #d8efe6; color: #076754;
}
.heroe {
    position: relative; isolation: isolate; overflow: hidden;
    display: flex; align-items: end; justify-content: space-between; gap: 1.3rem;
    padding: 1.7rem 2rem 1.85rem; border-radius: 1rem; color: #fff;
    background: radial-gradient(ellipse at 90% 8%, #174b48 0%, transparent 55%),
                linear-gradient(112deg, #102938 18%, #143838 100%);
}
.heroe::before {
    content: ""; position: absolute; z-index: -1; inset: 0 0 0 49%;
    background-image: linear-gradient(#c3eee517 1px, transparent 1px),
                      linear-gradient(90deg, #c3eee517 1px, transparent 1px);
    background-size: 29px 29px; mask-image: linear-gradient(90deg, transparent, #000);
}
.heroe .sobre-titulo {
    color: #aeedd9; font-size: .73rem; font-weight: 750;
    text-transform: uppercase; letter-spacing: .15em; margin: 0 0 .55rem;
}
.heroe h1 {
    font-size: clamp(2rem, 4vw, 3.3rem); color: #fff;
    font-weight: 750; line-height: 1.06; letter-spacing: -.046em; padding: 0; margin: 0;
}
.heroe .descripcion {
    color: #d1e3e4; font-size: .96rem; margin: .66rem 0 0; line-height: 1.46;
}
.heroe .contexto {
    display: flex; align-items: center; gap: .48rem; flex: none;
    background: #163c3e; border: 1px solid #548581; border-radius: .55rem;
    color: #e0f4ef; padding: .5rem .72rem; font-size: .78rem; font-weight: 600;
}
.contexto::before { content: ""; width: .48rem; height: .48rem;
    background: #8fe4c2; border-radius: 50%; }
.st-key-filtros, .st-key-controles_modelo {
    padding: .85rem 1rem .95rem; border: 1px solid var(--retail-borde);
    background: var(--retail-panel); border-radius: .85rem;
}
.st-key-navegacion button { min-height: 2.75rem; }
.stApp .st-key-navegacion button[role="radio"][aria-checked="true"] {
    border-color: #087a64; background: #ddf1e9; color: #075d4e;
}
.stApp .st-key-navegacion button[role="radio"][aria-checked="true"] p { color: #075d4e; }
.stApp button:focus-visible, .stApp summary:focus-visible {
    outline: 2px solid #087a64; outline-offset: 2px;
}
.tarjetas { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .9rem; }
.tarjetas.tres { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.tarjeta {
    min-width: 0; display: flex; flex-direction: column; gap: .31rem;
    padding: .82rem .95rem .78rem; border: 1px solid var(--retail-borde);
    border-radius: .83rem; background: var(--retail-panel);
}
.tarjeta-etiqueta { color: var(--retail-tenue); font-size: .79rem; font-weight: 650; }
.tarjeta-valor {
    color: var(--retail-texto); font-size: clamp(1.01rem, 2.16vw, 2rem); line-height: 1.14;
    letter-spacing: -.045em; font-weight: 750; overflow-wrap: anywhere;
    font-variant-numeric: tabular-nums;
}
.tarjeta-nota { color: var(--retail-tenue); font-size: .73rem; line-height: 1.27; }
.tarjeta-positiva { color: var(--retail-positivo); }
.tarjeta-negativa { color: var(--retail-negativo); }
.st-key-tendencia, .st-key-productos_top, .st-key-resultado_modelo,
.st-key-validacion_modelo { background: var(--retail-panel); }
.stApp [data-testid="stDownloadButton"] button { min-height: 2.75rem; }
.stApp [data-testid="stDownloadButton"] button:hover {
    border-color: #087a64; color: #075d4e;
}
@media (max-width: 900px) {
    [data-testid="stMainBlockContainer"] { padding-left: 1.65rem; padding-right: 1.65rem; }
}
@media (max-width: 700px) {
    [data-testid="stMainBlockContainer"] { padding: 2.7rem 1rem 2rem; }
    .st-key-navegacion button { padding-inline: .4rem; }
    .st-key-filtros [data-testid="stHorizontalBlock"],
    .st-key-controles_modelo [data-testid="stHorizontalBlock"] { row-gap: .65rem; }
    .heroe { flex-direction: column; align-items: start; gap: .9rem; padding: 1.2rem; }
    .heroe .descripcion { font-size: .89rem; }
    .tarjetas { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .55rem; }
    .tarjetas.tres { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .tarjetas.tres .tarjeta:last-child { grid-column: 1 / -1; }
    .tarjeta { padding: .7rem .68rem; }
    .tarjeta-valor { font-size: clamp(1.01rem, 4.45vw, 1.6rem); }
}
</style>
"""

CSS_OSCURO = """
<style>
.stApp {
    --retail-fondo: #122028; --retail-panel: #182932; --retail-borde: #3c515c;
    --retail-texto: #edf3f6; --retail-tenue: #c1d0d7;
    --retail-positivo: #93e3c3; --retail-negativo: #ffafb5;
}
.stApp button:focus-visible, .stApp summary:focus-visible { outline-color: #93e3c3; }
.stApp [data-testid="stDownloadButton"] button:hover { color: #93e3c3; }
</style>
"""

MARCA_HTML = """
<div class="marca">
  <span class="marca-icono" aria-hidden="true">
    <span style="font-size:1.25rem; line-height:1">▥</span>
  </span>
  Retail Sales Forecast
</div>
"""


@dataclass(frozen=True)
class Filtros:
    inicio: date
    fin: date
    sucursal_id: int | None
    categoria: str | None

    def parametros(self) -> dict[str, str | int | None]:
        return {"inicio": self.inicio.isoformat(), "fin": self.fin.isoformat(),
                "sucursal_id": self.sucursal_id, "categoria": self.categoria}


@dataclass(frozen=True)
class Informe:
    kpi: pd.Series
    anterior: pd.Series | None
    serie: pd.DataFrame
    categorias: pd.DataFrame
    productos: pd.DataFrame


@dataclass
class ModeloDemanda:
    estimador: Pipeline
    indicadores: pd.DataFrame
    inicio_prueba: date
    fin_prueba: date
    observaciones_prueba: int


@lru_cache(maxsize=1)
def consultas() -> dict[str, str]:
    """Carga las mismas consultas que documenta el repositorio."""
    bloques = SQL.read_text(encoding="utf-8").split("-- nombre: ")[1:]
    return {nombre.strip(): cuerpo.strip()
            for nombre, cuerpo in (bloque.split("\n", 1) for bloque in bloques)}


def conexion() -> sqlite3.Connection:
    return sqlite3.connect(f"{BD.as_uri()}?mode=ro", uri=True)


def consultar(con: sqlite3.Connection, nombre: str,
              parametros: dict[str, str | int | None] | None = None) -> pd.DataFrame:
    return pd.read_sql_query(consultas()[nombre], con, params=parametros)


@st.cache_data(max_entries=4, show_spinner=False)
def catalogo(firma: int) -> tuple[pd.Series, pd.DataFrame, pd.DataFrame]:
    with closing(conexion()) as con:
        return (consultar(con, "cobertura").iloc[0], consultar(con, "sucursales"),
                consultar(con, "productos"))


@st.cache_data(max_entries=48, show_spinner=False)
def informe_ventas(firma: int, filtros: Filtros, base_inicio: date) -> Informe:
    parametros = filtros.parametros()
    duracion = (filtros.fin - filtros.inicio).days + 1
    inicio_anterior = filtros.inicio - timedelta(days=duracion)
    with closing(conexion()) as con:
        anterior = None
        if inicio_anterior >= base_inicio:
            anterior = consultar(con, "kpi", {
                **parametros, "inicio": inicio_anterior.isoformat(),
                "fin": (filtros.inicio - timedelta(days=1)).isoformat(),
            }).iloc[0]
        return Informe(
            consultar(con, "kpi", parametros).iloc[0], anterior,
            consultar(con, "serie_diaria", parametros),
            consultar(con, "categorias", parametros),
            consultar(con, "productos_top", parametros),
        )


def preparar_detalle(detalle: pd.DataFrame) -> pd.DataFrame:
    detalle = detalle.copy()
    detalle["fecha"] = pd.to_datetime(detalle["fecha"]).dt.date
    detalle["descuento_pct"] = detalle["descuento_pct"] / 100
    for columna in detalle.filter(regex="_centavos$"):
        detalle[columna] = detalle[columna] / 100
    return detalle.rename(columns=COLUMNAS_DETALLE)


def detalle_filtrado(filtros: Filtros, limite: int = -1) -> pd.DataFrame:
    with closing(conexion()) as con:
        datos = consultar(con, "detalle", {**filtros.parametros(), "limite": limite})
    return preparar_detalle(datos)


def agregar_fila_excel(hoja, valores: tuple, formatos: dict[int, str] | None = None,
                       *, encabezado: bool = False) -> None:
    fila = list(valores)
    indices = range(len(fila)) if encabezado else (formatos or {})
    for indice in indices:
        celda = WriteOnlyCell(hoja, value=fila[indice])
        if encabezado:
            celda.fill = RELLENO_EXCEL
            celda.font = FUENTE_EXCEL
        elif formatos:
            celda.number_format = formatos[indice]
        fila[indice] = celda
    hoja.append(fila)


def exportar_excel(filtros: Filtros, informe: Informe, sucursal: str) -> bytes:
    kpi = informe.kpi
    margen = kpi["margen_pct"]
    resumen = [
        ("Desde", filtros.inicio, None), ("Hasta", filtros.fin, None),
        ("Sucursal", sucursal, None), ("Categoría", filtros.categoria or "Todas", None),
        ("Registros", int(kpi["registros"]), None), ("Unidades vendidas", int(kpi["unidades"]), None),
        ("Ingresos netos (USD)", kpi["ingresos_centavos"] / 100, FORMATO_EXCEL_USD),
        ("Utilidad bruta (USD)", kpi["utilidad_centavos"] / 100, FORMATO_EXCEL_USD),
        ("Margen bruto", margen / 100 if pd.notna(margen) else None, FORMATO_EXCEL_PCT),
    ]
    detalle = detalle_filtrado(filtros)
    libro = Workbook(write_only=True)
    hoja_resumen = libro.create_sheet("Resumen")
    hoja_ventas = libro.create_sheet("Ventas filtradas")
    for hoja, letras, anchos in (
        (hoja_resumen, "ABCDE", (25, 23, 24, 25, 17)),
        (hoja_ventas, "ABCDEFGHIJKLM", (14, 22, 18, 29, 17, 11, 13, 17, 17, 17, 18, 18, 18)),
    ):
        hoja.freeze_panes = "B2"
        for columna, ancho in zip(letras, anchos, strict=True):
            hoja.column_dimensions[columna].width = ancho

    agregar_fila_excel(hoja_resumen, ("Indicador", "Valor"), encabezado=True)
    for etiqueta, valor, formato in resumen:
        agregar_fila_excel(hoja_resumen, (etiqueta, valor), {1: formato} if formato else None)
    hoja_resumen.append(())
    hoja_resumen.append(())
    agregar_fila_excel(hoja_resumen, ("Categoría", "Unidades", "Ingresos netos (USD)",
                                    "Utilidad bruta (USD)", "Margen bruto"), encabezado=True)
    formatos_categoria = {2: FORMATO_EXCEL_USD, 3: FORMATO_EXCEL_USD, 4: FORMATO_EXCEL_PCT}
    for fila in informe.categorias.itertuples(index=False):
        agregar_fila_excel(hoja_resumen, (
            fila.categoria, fila.unidades, fila.ingresos_centavos / 100,
            fila.utilidad_centavos / 100, fila.margen_pct / 100 if pd.notna(fila.margen_pct) else None,
        ), formatos_categoria)

    agregar_fila_excel(hoja_ventas, tuple(detalle.columns), encabezado=True)
    formatos_detalle = {6: FORMATO_EXCEL_PCT, **dict.fromkeys(range(7, 13), FORMATO_EXCEL_USD)}
    for fila in detalle.itertuples(index=False, name=None):
        agregar_fila_excel(hoja_ventas, fila, formatos_detalle)
    hoja_ventas.auto_filter.ref = f"A1:M{len(detalle) + 1}"
    with BytesIO() as memoria:
        libro.save(memoria)
        return memoria.getvalue()


def variables_modelo(datos: pd.DataFrame) -> pd.DataFrame:
    calendario = pd.to_datetime(datos["fecha"]).dt
    return pd.DataFrame({
        "sucursal_producto": datos["sucursal_id"].astype(str) + "-"
                             + datos["producto_id"].astype(str),
        "categoria_mes": datos["categoria"] + "-" + calendario.month.astype(str),
        "dia_semana": calendario.day_of_week,
        "log_precio_relativo": np.log(datos["precio_relativo"]) * 10,
        "descuento_relativo": datos["descuento_pct"] / 30,
        "quincena": calendario.day.isin([1, 2, 14, 15, 16, 29, 30, 31]).astype(int),
        "fiestas": ((calendario.month == 12) & (calendario.day >= 15)).astype(int),
        "tendencia_anual": calendario.year - 2024 + (calendario.day_of_year - 1) / 365.25,
    })


def nuevo_estimador() -> Pipeline:
    preparar = ColumnTransformer(
        [("categorias", OneHotEncoder(handle_unknown="ignore"), CATEGORICAS)],
        remainder="passthrough",
    )
    return make_pipeline(preparar, PoissonRegressor(alpha=0.002, max_iter=300))


@st.cache_resource(max_entries=2, show_spinner=False)
def entrenar(firma: int) -> ModeloDemanda:
    with closing(conexion()) as con:
        datos = consultar(con, "entrenamiento")
    datos["fecha"] = pd.to_datetime(datos["fecha"])
    fin = datos["fecha"].max()
    corte = fin - pd.Timedelta(days=55)
    variables = variables_modelo(datos)
    previo = datos["fecha"] < corte
    y_prueba = datos.loc[~previo, "unidades"]

    # La referencia solo usa filas de entrenamiento, incluso para el último día de prueba.
    claves = ["sucursal_producto", "dia_semana"]
    base = variables.loc[previo, claves].assign(unidades=datos.loc[previo, "unidades"])
    perfil = base.groupby(claves)["unidades"].median().rename("referencia")
    referencia = variables.loc[~previo, claves].join(perfil, on=claves)["referencia"]
    referencia = referencia.fillna(base["unidades"].median()).to_numpy()

    evaluado = nuevo_estimador().fit(variables.loc[previo], datos.loc[previo, "unidades"])
    pronostico = evaluado.predict(variables.loc[~previo])

    def evaluar(nombre: str, valores: np.ndarray) -> dict[str, float | str]:
        error = np.abs(y_prueba.to_numpy() - valores)
        return {
            "Método": nombre,
            "MAE (unidades)": float(mean_absolute_error(y_prueba, valores)),
            "WAPE": float(error.sum() / y_prueba.sum()) if y_prueba.sum() else np.nan,
        }

    indicadores = pd.DataFrame([
        evaluar("Regresión de Poisson", pronostico), evaluar("Mediana histórica", referencia),
    ])
    # El simulador aprovecha todo el historial una vez cerrada la evaluación.
    final = nuevo_estimador().fit(variables, datos["unidades"])
    return ModeloDemanda(final, indicadores, corte.date(), fin.date(), len(y_prueba))


@st.cache_data(max_entries=128, show_spinner=False)
def precios_observados(firma: int, sucursal_id: int, producto_id: int) -> pd.Series:
    with closing(conexion()) as con:
        resultado = consultar(con, "precios_escenario",
                              {"sucursal_id": sucursal_id, "producto_id": producto_id})
    return resultado.iloc[0]


def predecir_escenarios(modelo: ModeloDemanda, fecha: date, sucursal_id: int, producto_id: int,
                        categoria: str, precio_centavos: int, referencia: int,
                        descuento: int) -> np.ndarray:
    escenarios = pd.DataFrame({
        "fecha": [fecha, fecha], "sucursal_id": sucursal_id, "producto_id": producto_id,
        "categoria": categoria, "precio_relativo": precio_centavos / referencia,
        "descuento_pct": [0, descuento],
    })
    return modelo.estimador.predict(variables_modelo(escenarios))


def numero(valor: float, decimales: int = 0) -> str:
    return f"{valor:,.{decimales}f}".translate(str.maketrans(",.", ".,"))


def usd(centavos: float, decimales: int = 0) -> str:
    return f"USD {numero(centavos / 100, decimales)}"


def porcentaje(valor: float) -> str:
    return f"{numero(valor, 1)} %" if pd.notna(valor) else "—"


def fecha_corta(valor: date, incluir_ano: bool = False) -> str:
    texto = f"{valor.day:02d} {MESES[valor.month - 1]}"
    return f"{texto} {valor.year}" if incluir_ano else texto


def cambio_periodo(actual: float, previo: float, puntos: bool = False) -> tuple[str, str]:
    if pd.isna(actual) or pd.isna(previo) or (not puntos and previo == 0):
        return "Sin base de comparación", ""
    cambio = actual - previo
    if not puntos:
        cambio = cambio / abs(previo) * 100
    estilo = "tarjeta-positiva" if cambio > 0 else "tarjeta-negativa" if cambio < 0 else ""
    signo = "+" if cambio > 0 else "−" if cambio < 0 else ""
    unidad = "pp" if puntos else "%"
    return f"{signo}{numero(abs(cambio), 1)} {unidad} vs. período anterior", estilo


def tarjetas(valores: list[tuple[str, str, str, str]]) -> None:
    piezas = []
    for titulo, valor, nota, estilo in valores:
        piezas.append(f"""
          <div class="tarjeta">
            <div class="tarjeta-etiqueta">{escape(titulo)}</div>
            <div class="tarjeta-valor">{escape(valor)}</div>
            <div class="tarjeta-nota {estilo}">{escape(nota)}</div>
          </div>
        """)
    clases = "tarjetas tres" if len(valores) == 3 else "tarjetas"
    st.html(f'<div class="{clases}">' + "".join(piezas) + "</div>")


def mostrar_kpis(informe: Informe) -> None:
    kpi, previo = informe.kpi, informe.anterior
    indicadores = [
        ("Ingresos netos", "ingresos_centavos", usd(kpi["ingresos_centavos"], 2)),
        ("Unidades vendidas", "unidades", numero(kpi["unidades"])),
        ("Utilidad bruta", "utilidad_centavos", usd(kpi["utilidad_centavos"], 2)),
        ("Margen bruto", "margen_pct", porcentaje(kpi["margen_pct"])),
    ]
    tarjetas([
        (titulo, valor, *(cambio_periodo(kpi[clave], previo[clave], clave == "margen_pct")
                          if previo is not None else ("Sin período anterior completo", "")))
        for titulo, clave, valor in indicadores
    ])


@st.cache_resource
def bloqueo_graficos() -> Lock:
    return Lock()


def estilo_ejes(ejes: Axes, eje_cuadricula: str) -> None:
    sns.despine(ax=ejes, left=True, bottom=True)
    ejes.set_axisbelow(True)
    ejes.grid(axis=eje_cuadricula, color=GRILLA, linewidth=0.8)
    ejes.tick_params(axis="both", colors=TENUE, labelsize=11, length=0, pad=7)


def tendencia(serie: pd.DataFrame) -> Figure:
    fechas = pd.to_datetime(serie["fecha"])
    ventas = serie["ingresos_centavos"] / 100
    figura = Figure(figsize=(8.3, 3.2), layout="constrained")
    ejes = figura.subplots()
    estilo_ejes(ejes, "y")
    ejes.fill_between(fechas, ventas, 0, color="#dff1ea", linewidth=0)
    ejes.plot(fechas, ventas, color=VERDE, linewidth=1.8,
              marker="o" if len(serie) < 8 else None, markersize=4, label="Por día")
    if len(serie) >= 7:
        ejes.plot(fechas, ventas.rolling(7, min_periods=7).mean(), color="#244c6b",
                  linewidth=2, label="Media de 7 días")
        ejes.legend(loc="upper left", frameon=False, labelcolor=TINTA, fontsize=11,
                    ncols=2, borderaxespad=0.3)
    ejes.set_ylim(0, max(float(ventas.max()) * 1.27, 1))
    ejes.yaxis.set_major_locator(MaxNLocator(nbins=4, integer=True))
    ejes.yaxis.set_major_formatter(FuncFormatter(lambda valor, _: numero(valor)))
    ejes.set_ylabel("USD", color=TENUE, fontsize=11)
    ejes.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=6))
    duracion = (fechas.iloc[-1] - fechas.iloc[0]).days
    if duracion:
        medio_dia = pd.Timedelta(hours=11)
        ejes.set_xlim(fechas.iloc[0] - medio_dia, fechas.iloc[-1] + medio_dia)
        ejes.xaxis.set_major_formatter(FuncFormatter(
            lambda valor, _: fecha_corta(mdates.num2date(valor), duracion >= 365),
        ))
    else:
        dia = fechas.iloc[0]
        ejes.set_xlim(dia - pd.Timedelta(hours=14), dia + pd.Timedelta(hours=14))
        ejes.set_xticks([dia], labels=[fecha_corta(dia)])
    ejes.margins(x=0.02)
    return figura


def ranking(productos: pd.DataFrame) -> Figure:
    datos = productos.assign(ingresos=productos["ingresos_centavos"] / 100)
    figura = Figure(figsize=(5.7, 3.2), layout="constrained")
    ejes = figura.subplots()
    estilo_ejes(ejes, "x")
    posiciones = range(len(datos))
    colores = sns.color_palette(["#087a64", "#2b91a0", "#50a8ae", "#68b6b3", "#83c3b9"])
    barras = ejes.barh(posiciones, datos["ingresos"], color=colores[:len(datos)], height=0.55)
    ejes.set_yticks(posiciones, labels=datos["producto"].tolist())
    ejes.invert_yaxis()
    ejes.bar_label(barras, labels=[numero(valor) for valor in datos["ingresos"]],
                   padding=5, color=TINTA, fontsize=11)
    ejes.set_xlim(0, max(1, float(datos["ingresos"].max()) * 1.3))
    ejes.xaxis.set_major_locator(MaxNLocator(nbins=4, integer=True))
    ejes.xaxis.set_major_formatter(FuncFormatter(lambda valor, _: numero(valor)))
    ejes.set_xlabel("USD", color=TENUE, fontsize=11)
    return figura


def cabecera(vista: str, cobertura: pd.Series, sucursales: pd.DataFrame,
             productos: pd.DataFrame) -> None:
    if vista == MONITOR:
        titulo = "Monitor de ventas"
        descripcion = "Consulta ingresos, unidades y rentabilidad por período, sucursal y categoría."
        contexto = f"{len(sucursales)} sucursales · {len(productos)} productos"
    else:
        titulo = "Simulador de demanda"
        descripcion = "Estima cuántas unidades se venderían con un precio y descuento determinados."
        fin = date.fromisoformat(cobertura["fin"])
        contexto = f"Datos hasta el {fecha_corta(fin, incluir_ano=True)}"
    st.html(f"""
    <section class="heroe">
      <div>
        <p class="sobre-titulo">Datos sintéticos</p>
        <h1>{titulo}</h1>
        <p class="descripcion">{descripcion}</p>
      </div>
      <span class="contexto">{contexto}</span>
    </section>
    """)


def mostrar_monitor(firma: int, cobertura: pd.Series, sucursales: pd.DataFrame,
                    productos: pd.DataFrame) -> None:
    inicio = date.fromisoformat(cobertura["inicio"])
    fin = date.fromisoformat(cobertura["fin"])
    nombres = sucursales.set_index("sucursal_id")["nombre"].to_dict()
    categorias = sorted(productos["categoria"].unique())
    with st.container(key="filtros"):
        fechas, tiendas, familias = st.columns([1.24, 1, 1], gap="medium")
        periodo = fechas.date_input(
            "Período de ventas", (max(inicio, fin - timedelta(days=89)), fin),
            min_value=inicio, max_value=fin, format="DD/MM/YYYY", key="monitor_periodo",
        )
        sucursal = tiendas.selectbox(
            "Sucursal", [None, *nombres], format_func=lambda x: nombres.get(x, "Todas"),
            key="monitor_sucursal",
        )
        categoria = familias.selectbox(
            "Categoría", [None, *categorias], format_func=lambda x: x or "Todas",
            key="monitor_categoria",
        )

    if len(periodo) != 2:
        st.info("Selecciona la fecha de fin para consultar el período.")
        return
    filtros = Filtros(*periodo, sucursal, categoria)
    informe = informe_ventas(firma, filtros, inicio)
    if not informe.kpi["registros"]:
        st.info("No hay registros para estos filtros. Prueba otro período, sucursal o categoría.")
        return

    mostrar_kpis(informe)
    evolucion, destacados = st.columns([1.42, 1], gap="medium")
    with evolucion.container(border=True, key="tendencia"):
        st.subheader("Evolución de ingresos")
        st.caption("Ingresos netos diarios en el período seleccionado")
        with bloqueo_graficos():
            st.pyplot(tendencia(informe.serie),
                      alt="Gráfico de línea con los ingresos por día y la media móvil de 7 días "
                          "cuando el período lo permite.")
    with destacados.container(border=True, key="productos_top"):
        st.subheader("Productos líderes")
        st.caption("Hasta cinco productos por ingresos netos")
        with bloqueo_graficos():
            st.pyplot(ranking(informe.productos),
                      alt="Barras horizontales de los productos con más ingresos netos en USD.")

    etiqueta, accion = st.columns([2.1, 1], vertical_alignment="center")
    etiqueta.subheader("Detalle de ventas")
    accion.download_button(
        "Descargar Excel", data=lambda: exportar_excel(filtros, informe, nombres.get(sucursal, "Todas")),
        file_name=f"ventas_{filtros.inicio.isoformat()}_{filtros.fin.isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        on_click="ignore", icon=":material/download:", width="stretch",
        help="Incluye el resumen de indicadores y todas las filas del período filtrado.",
        key="descargar_excel",
    )
    with st.expander("Ver detalle y datos de los gráficos", key="detalle", on_change="rerun") as vista:
        if vista.open:
            st.caption(f"Vista previa de {numero(min(200, informe.kpi['registros']))} de "
                       f"{numero(informe.kpi['registros'])} registros. El Excel incluye el detalle completo.")
            st.dataframe(detalle_filtrado(filtros, limite=200), hide_index=True,
                         column_config={
                             "Fecha": st.column_config.DateColumn(format="DD/MM/YYYY"),
                             "Descuento": st.column_config.NumberColumn(format="percent"),
                             **{titulo: st.column_config.NumberColumn(format="USD %.2f")
                                for clave, titulo in COLUMNAS_DETALLE.items()
                                if clave.endswith("_centavos")},
                         })
            serie = informe.serie.assign(
                ingresos_centavos=informe.serie["ingresos_centavos"] / 100,
            ).rename(columns={"fecha": "Fecha", "ingresos_centavos": "Ingresos netos (USD)"})
            serie["Media de 7 días (USD)"] = serie["Ingresos netos (USD)"].rolling(7).mean()
            ranking_datos = informe.productos.assign(
                ingresos_centavos=informe.productos["ingresos_centavos"] / 100,
            ).rename(columns={"producto": "Producto", "unidades": "Unidades",
                              "ingresos_centavos": "Ingresos netos (USD)"})
            st.markdown("**Ingresos por día**")
            st.dataframe(serie, hide_index=True)
            st.markdown("**Productos por ingresos netos**")
            st.dataframe(ranking_datos, hide_index=True)


def mostrar_simulador(firma: int, cobertura: pd.Series, sucursales: pd.DataFrame,
                       productos: pd.DataFrame) -> None:
    nombres = sucursales.set_index("sucursal_id")["nombre"].to_dict()
    catalogo_productos = productos.set_index("producto_id")
    fin = date.fromisoformat(cobertura["fin"])
    with st.container(key="controles_modelo"):
        tienda, articulo, dia = st.columns([1, 1.35, 1], gap="medium")
        sucursal_id = tienda.selectbox("Sucursal", list(nombres),
                                      format_func=nombres.__getitem__, key="sim_sucursal")
        producto_id = articulo.selectbox("Producto", list(catalogo_productos.index),
                                         format_func=catalogo_productos["nombre"].__getitem__,
                                         key="sim_producto")
        fecha = dia.date_input("Fecha simulada", fin + timedelta(days=1),
                               min_value=fin + timedelta(days=1), max_value=fin + timedelta(days=90),
                               format="DD/MM/YYYY", key="sim_fecha")
        precios = precios_observados(firma, sucursal_id, producto_id)
        importes, descuento = st.columns([1, 1.7], gap="medium")
        precio = importes.number_input(
            "Precio de lista (USD)", float(precios["minimo"] / 100), float(precios["maximo"] / 100),
            float(precios["reciente"] / 100), step=0.01, format="%.2f",
            key=f"sim_precio_{sucursal_id}_{producto_id}",
            help="Puedes usar el rango de precios observado para este producto y sucursal.",
        )
        promocion = descuento.slider("Descuento del escenario (%)", 0, 30, 15,
                                     step=5, key="sim_descuento")

    with st.spinner("Preparando el modelo y la evaluación histórica…"):
        modelo = entrenar(firma)
    centavos = round(precio * 100)
    referencia = int(precios["referencia"])
    base, escenario = predecir_escenarios(
        modelo, fecha, sucursal_id, producto_id, catalogo_productos.at[producto_id, "categoria"],
        centavos, referencia, promocion,
    )
    precio_neto = (centavos * (100 - promocion) + 50) // 100
    variacion = (escenario - base) / base * 100 if base > 0 else np.nan
    estilo = "tarjeta-positiva" if variacion > 0 else "tarjeta-negativa" if variacion < 0 else ""
    signo = "+" if variacion > 0 else ""
    with st.container(border=True, key="resultado_modelo"):
        st.subheader("Demanda estimada")
        st.caption(f"{nombres[sucursal_id]} · {catalogo_productos.at[producto_id, 'nombre']} · "
                   f"{fecha_corta(fecha, incluir_ano=True)}")
        tarjetas([
            ("Sin descuento", f"{numero(base, 1)} u.", f"Precio neto {usd(centavos, 2)}", ""),
            ("Con descuento", f"{numero(escenario, 1)} u.", f"Precio neto {usd(precio_neto, 2)}", ""),
            ("Variación estimada", signo + porcentaje(variacion),
             "Frente al mismo precio de lista sin descuento", estilo),
        ])
        st.caption("La estimación predice unidades vendidas en un día según patrones sintéticos. "
                   "La variación expresa una comparación del modelo entre los dos escenarios.")

    with st.container(border=True, key="validacion_modelo"):
        st.subheader("Evaluación histórica")
        st.caption(f"{fecha_corta(modelo.inicio_prueba, incluir_ano=True)} al "
                   f"{fecha_corta(modelo.fin_prueba, incluir_ano=True)} · "
                   f"{numero(modelo.observaciones_prueba)} observaciones de prueba")
        st.dataframe(
            modelo.indicadores, hide_index=True,
            column_config={"MAE (unidades)": st.column_config.NumberColumn(format="%.2f"),
                           "WAPE": st.column_config.NumberColumn(format="percent")},
        )
        st.caption("La referencia usa la mediana del historial de entrenamiento para la misma "
                   "sucursal, producto y día de la semana. Valores menores de MAE y WAPE "
                   "indican menor error.")


def main() -> None:
    st.set_page_config(page_title="Retail Sales Forecast", page_icon=":material/monitoring:",
                       layout="wide")
    st.html(CSS + (CSS_OSCURO if st.context.theme.type == "dark" else ""))
    st.html(MARCA_HTML)

    try:
        firma = BD.stat().st_mtime_ns
        cobertura, sucursales, productos = catalogo(firma)
        if not cobertura["registros"] or sucursales.empty or productos.empty:
            st.error("La base de ventas está vacía. Regenera los datos con data/generar_datos.py.")
            return

        with st.container(key="navegacion"):
            vista = st.segmented_control("Vista", [MONITOR, SIMULADOR], default=MONITOR,
                                         required=True, label_visibility="collapsed", key="vista")
        cabecera(vista, cobertura, sucursales, productos)
        if vista == MONITOR:
            mostrar_monitor(firma, cobertura, sucursales, productos)
        else:
            mostrar_simulador(firma, cobertura, sucursales, productos)
    except (OSError, sqlite3.Error, pd.errors.DatabaseError):
        LOG.exception("No se pudo leer el origen de datos de retail")
        st.error("No se pudo cargar la base de ventas o las consultas. Verifica los archivos "
                 "del proyecto y ejecuta data/generar_datos.py para regenerar los datos.")


if __name__ == "__main__":
    main()
