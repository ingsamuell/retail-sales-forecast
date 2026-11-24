const porId = id => document.getElementById(id);
const DIA = 86_400_000;
const numero = new Intl.NumberFormat("es-VE");
const decimal = new Intl.NumberFormat("es-VE", {minimumFractionDigits: 1, maximumFractionDigits: 1});
const moneda = new Intl.NumberFormat("es-VE", {style: "currency", currency: "USD", currencyDisplay: "code"});
const porcentaje = valor => `${decimal.format(valor)} %`;
const dinero = centavos => moneda.format(centavos / 100);
const fechaISO = tiempo => new Date(tiempo).toISOString().slice(0, 10);

function crear(tag, texto, clase) {
  const elemento = document.createElement(tag);
  if (texto !== undefined) elemento.textContent = texto;
  if (clase) elemento.className = clase;
  return elemento;
}

function opcion(select, valor, etiqueta) {
  const fila = crear("option", etiqueta);
  fila.value = valor;
  select.append(fila);
}

function tarjetas(contenedor, indicadores) {
  contenedor.replaceChildren(...indicadores.map(([etiqueta, valor]) => {
    const tarjeta = crear("div", undefined, "tarjeta");
    tarjeta.append(crear("h3", etiqueta), crear("strong", valor));
    return tarjeta;
  }));
}

function dibujarSerie(serie) {
  const canvas = porId("tendencia");
  if (!canvas.clientWidth) return;
  const ancho = canvas.clientWidth;
  const alto = canvas.clientHeight;
  const escala = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = ancho * escala;
  canvas.height = alto * escala;
  const contexto = canvas.getContext("2d");
  contexto.scale(escala, escala);
  const izquierda = 58;
  const derecha = ancho - 12;
  const base = alto - 26;
  const techo = 16;
  const columnas = Math.max(1, serie.length - 1);
  const pico = Math.max(1, ...serie);
  const unidad = 10 ** Math.floor(Math.log10(pico / 100));
  const maximo = Math.ceil(pico / (unidad * 25)) * unidad * 25;
  const px = indice => izquierda + (derecha - izquierda) * (serie.length === 1 ? .5 : indice / columnas);
  const py = valor => base - (base - techo) * valor / maximo;

  contexto.font = "12px system-ui";
  contexto.textBaseline = "middle";
  contexto.textAlign = "right";
  contexto.lineWidth = 1;
  for (let paso = 0; paso <= 4; paso += 1) {
    const monto = maximo * paso / 4;
    const y = py(monto);
    contexto.beginPath();
    contexto.moveTo(izquierda, y);
    contexto.lineTo(derecha, y);
    contexto.strokeStyle = "#d4e0db";
    contexto.stroke();
    contexto.fillStyle = "#455e63";
    contexto.fillText(numero.format(Math.round(monto / 100)), izquierda - 7, y);
  }

  if (serie.length > 1) {
    const dibujar = () => serie.forEach((valor, indice) => {
      if (indice === 0) contexto.moveTo(px(indice), py(valor));
      else contexto.lineTo(px(indice), py(valor));
    });
    contexto.beginPath();
    dibujar();
    contexto.lineTo(derecha, base);
    contexto.lineTo(izquierda, base);
    contexto.closePath();
    contexto.fillStyle = "#e0f1e9";
    contexto.fill();
    contexto.beginPath();
    dibujar();
    contexto.strokeStyle = "#087a64";
    contexto.lineWidth = 2;
    contexto.stroke();
  } else if (serie.length) {
    contexto.beginPath();
    contexto.arc(px(0), py(serie[0]), 4, 0, 2 * Math.PI);
    contexto.fillStyle = "#087a64";
    contexto.fill();
  }
  contexto.fillStyle = "#455e63";
  contexto.textAlign = "left";
  contexto.fillText("USD", izquierda, alto - 9);
}

function prediccion(modelo, sucursal, producto, categoria, fecha, precio, referencia, descuento) {
  const ano = fecha.getUTCFullYear();
  const mes = fecha.getUTCMonth() + 1;
  const dia = fecha.getUTCDate();
  const diaSemana = (fecha.getUTCDay() + 6) % 7;
  const diaDelAno = (fecha.getTime() - Date.UTC(ano, 0, 1)) / DIA;
  const claves = [`sucursal_producto_${sucursal}-${producto}`, `categoria_mes_${categoria}-${mes}`, `dia_semana_${diaSemana}`];
  const numericas = [
    Math.log(precio / referencia) * 10,
    descuento / 30,
    Number([1, 2, 14, 15, 16, 29, 30, 31].includes(dia)),
    Number(mes === 12 && dia >= 15),
    ano - 2024 + diaDelAno / 365.25,
  ];
  const categoricas = claves.reduce((total, clave) => total + (modelo.categorias[clave] ?? 0), 0);
  const continuas = numericas.reduce((total, valor, indice) => total + valor * modelo.numericas[indice], 0);
  return Math.exp(modelo.intercepto + categoricas + continuas);
}

function iniciar(datos) {
  const sucursales = new Map(datos.sucursales);
  const productos = new Map(datos.productos.map(([id, nombre, categoria]) => [id, {nombre, categoria}]));
  const inicio = Date.parse(datos.inicio);
  const fin = Date.parse(datos.fin);
  const filtros = porId("filtros").elements;
  const escenario = porId("escenario").elements;
  const indicadorFiltro = porId("estado-filtros");
  const indicadorEscenario = porId("estado-escenario");
  const botonExportar = porId("exportar");
  const estadoExportar = porId("estado-exportar");
  let seleccion;
  let serieActual = [];
  let exportando = false;

  for (const [id, nombre] of sucursales) {
    opcion(filtros.sucursal, id, nombre);
    opcion(escenario.sucursal, id, nombre);
  }
  for (const categoria of [...new Set(datos.productos.map(fila => fila[2]))].sort()) {
    opcion(filtros.categoria, categoria, categoria);
  }
  for (const [id, producto] of productos) {
    opcion(escenario.producto, id, producto.nombre);
  }
  for (const campo of [filtros.desde, filtros.hasta]) {
    campo.min = datos.inicio;
    campo.max = datos.fin;
  }
  filtros.desde.value = fechaISO(Math.max(inicio, fin - 89 * DIA));
  filtros.hasta.value = datos.fin;
  escenario.fecha.min = fechaISO(fin + DIA);
  escenario.fecha.max = fechaISO(fin + 90 * DIA);
  escenario.fecha.value = escenario.fecha.min;

  function actualizarMonitor() {
    const desde = (Date.parse(filtros.desde.value) - inicio) / DIA;
    const hasta = (Date.parse(filtros.hasta.value) - inicio) / DIA;
    const sucursal = Number(filtros.sucursal.value);
    const categoria = filtros.categoria.value;
    const valido = filtros.desde.validity.valid && filtros.hasta.validity.valid && desde <= hasta;
    indicadorFiltro.classList.toggle("visualmente-oculto", valido);
    porId("kpi").hidden = !valido;
    porId("graficos").hidden = !valido;
    if (!valido) {
      seleccion = undefined;
      botonExportar.disabled = true;
      indicadorFiltro.textContent = "Selecciona un período válido dentro del historial.";
      return;
    }
    const filas = datos.ventas.filter(([dia, tienda, producto]) =>
      dia >= desde && dia <= hasta && (!sucursal || tienda === sucursal) &&
      (!categoria || productos.get(producto).categoria === categoria)
    );
    const serie = Array(hasta - desde + 1).fill(0);
    const ranking = new Map();
    let ingresos = 0;
    let unidades = 0;
    let utilidad = 0;
    for (const [dia, , producto, cantidad, , , precioNeto, costo] of filas) {
      const neto = cantidad * precioNeto;
      ingresos += neto;
      unidades += cantidad;
      utilidad += neto - cantidad * costo;
      serie[dia - desde] += neto;
      ranking.set(producto, (ranking.get(producto) ?? 0) + neto);
    }
    const margen = ingresos ? 100 * utilidad / ingresos : null;
    seleccion = {
      filas, ingresos, unidades, utilidad, margen,
      desde: filtros.desde.value, hasta: filtros.hasta.value, sucursal, categoria,
    };
    botonExportar.disabled = exportando || !filas.length;
    indicadorFiltro.textContent = `${numero.format(filas.length)} filas en el período filtrado.`;
    tarjetas(porId("kpi"), [
      ["Ingresos netos", dinero(ingresos)], ["Unidades vendidas", numero.format(unidades)],
      ["Utilidad bruta", dinero(utilidad)], ["Margen bruto", margen === null ? "—" : porcentaje(margen)],
    ]);
    serieActual = serie;
    dibujarSerie(serie);
    porId("resumen-tendencia").textContent =
      `${seleccion.desde} al ${seleccion.hasta} · Promedio diario ${dinero(ingresos / serie.length)}`;

    const orden = [...ranking].sort(([idA, a], [idB, b]) =>
      b - a || productos.get(idA).nombre.localeCompare(productos.get(idB).nombre, "es")
    ).slice(0, 5);
    porId("productos-lideres").replaceChildren(...orden.map(([id, monto]) => {
      const item = crear("li");
      const barra = crear("progress");
      barra.max = Math.max(orden[0][1], 1);
      barra.value = monto;
      barra.setAttribute("aria-hidden", "true");
      item.append(crear("span", productos.get(id).nombre), crear("span", dinero(monto)), barra);
      return item;
    }));
  }

  function cambiarPrecio() {
    const [minimo, maximo, habitual] = datos.precios[`${escenario.sucursal.value}-${escenario.producto.value}`];
    escenario.precio.min = (minimo / 100).toFixed(2);
    escenario.precio.max = (maximo / 100).toFixed(2);
    escenario.precio.value = (habitual / 100).toFixed(2);
  }

  function actualizarEscenario() {
    const sucursal = Number(escenario.sucursal.value);
    const producto = Number(escenario.producto.value);
    const [minimo, maximo, , referencia] = datos.precios[`${sucursal}-${producto}`];
    const precio = Math.round(escenario.precio.valueAsNumber * 100);
    const descuento = escenario.descuento.valueAsNumber;
    porId("valor-descuento").value = `${descuento} %`;
    if (!escenario.fecha.validity.valid || !escenario.precio.validity.valid) {
      indicadorEscenario.textContent = `Elige una fecha válida y un precio entre ${dinero(minimo)} y ${dinero(maximo)}.`;
      porId("resultado").replaceChildren();
      return;
    }
    const fecha = new Date(Date.parse(escenario.fecha.value));
    const categoria = productos.get(producto).categoria;
    const base = prediccion(datos.modelo, sucursal, producto, categoria, fecha, precio, referencia, 0);
    const promocion = prediccion(datos.modelo, sucursal, producto, categoria, fecha, precio, referencia, descuento);
    tarjetas(porId("resultado"), [
      ["Sin descuento", `${decimal.format(base)} u.`],
      ["Con descuento", `${decimal.format(promocion)} u.`],
      ["Variación estimada", porcentaje(100 * (promocion / base - 1))],
    ]);
    indicadorEscenario.textContent = `Precio neto con descuento ${dinero(Math.floor((precio * (100 - descuento) + 50) / 100))}.`;
  }

  porId("metricas").replaceChildren(...datos.modelo.metricas.map(metrica => {
    const fila = crear("tr");
    fila.append(crear("td", metrica["Método"]), crear("td", metrica["MAE (unidades)"].toFixed(2).replace(".", ",")),
      crear("td", `${(metrica.WAPE * 100).toFixed(2).replace(".", ",")} %`));
    return fila;
  }));

  porId("filtros").addEventListener("input", actualizarMonitor);
  porId("filtros").addEventListener("submit", evento => evento.preventDefault());
  porId("escenario").addEventListener("input", evento => {
    if (["sucursal", "producto"].includes(evento.target.name)) cambiarPrecio();
    actualizarEscenario();
  });
  porId("escenario").addEventListener("submit", evento => evento.preventDefault());
  for (const vista of document.querySelectorAll('input[name="vista"]')) {
    vista.addEventListener("change", () => {
      porId("monitor").hidden = vista.value !== "monitor";
      porId("simulador").hidden = vista.value !== "simulador";
      if (vista.value === "monitor") dibujarSerie(serieActual);
    });
  }
  new ResizeObserver(() => dibujarSerie(serieActual)).observe(porId("tendencia"));

  botonExportar.addEventListener("click", async () => {
    if (!seleccion || exportando) return;
    const informe = seleccion;
    exportando = true;
    botonExportar.disabled = true;
    estadoExportar.textContent = "Preparando el libro…";
    try {
      const xlsx = await import("https://cdn.sheetjs.com/xlsx-0.20.3/package/xlsx.mjs");
      const resumen = [
        ["Indicador", "Valor"], ["Desde", informe.desde], ["Hasta", informe.hasta],
        ["Sucursal", sucursales.get(informe.sucursal) ?? "Todas"],
        ["Categoría", informe.categoria || "Todas"], ["Registros", informe.filas.length],
        ["Unidades vendidas", informe.unidades], ["Ingresos netos (USD)", informe.ingresos / 100],
        ["Utilidad bruta (USD)", informe.utilidad / 100], ["Margen bruto (%)", informe.margen],
      ];
      const detalle = [["Fecha", "Sucursal", "Producto", "Categoría", "Unidades", "Descuento (%)",
        "Precio de lista (USD)", "Precio neto (USD)", "Ingresos netos (USD)", "Utilidad bruta (USD)"]];
      for (const [dia, sucursal, producto, cantidad, precioLista, descuento, precioNeto, costo] of informe.filas) {
        const {nombre, categoria} = productos.get(producto);
        detalle.push([fechaISO(inicio + dia * DIA), sucursales.get(sucursal), nombre, categoria, cantidad,
          descuento, precioLista / 100, precioNeto / 100, cantidad * precioNeto / 100,
          cantidad * (precioNeto - costo) / 100]);
      }
      const libro = xlsx.utils.book_new();
      xlsx.utils.book_append_sheet(libro, xlsx.utils.aoa_to_sheet(resumen), "Resumen");
      xlsx.utils.book_append_sheet(libro, xlsx.utils.aoa_to_sheet(detalle), "Ventas filtradas");
      xlsx.writeFile(libro, `ventas_${informe.desde}_${informe.hasta}.xlsx`, {compression: true});
      estadoExportar.textContent = "Excel generado.";
    } catch {
      estadoExportar.textContent = "No se pudo generar el Excel. Vuelve a intentarlo.";
    } finally {
      exportando = false;
      botonExportar.disabled = !seleccion?.filas.length;
    }
  });

  porId("estado").hidden = true;
  porId("interfaz").hidden = false;
  cambiarPrecio();
  actualizarMonitor();
  actualizarEscenario();
}

try {
  const respuesta = await fetch("datos.json");
  if (!respuesta.ok) throw new Error(`HTTP ${respuesta.status}`);
  iniciar(await respuesta.json());
} catch {
  const estado = porId("estado");
  estado.replaceChildren("No se pudieron cargar los datos. ", crear("a", "Recargar la demo"));
  estado.lastChild.href = "demo.html";
  estado.hidden = false;
  porId("interfaz").hidden = true;
}
