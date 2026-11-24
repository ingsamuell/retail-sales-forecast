-- Las secciones marcadas con `-- nombre:` son consultas independientes.
-- v_ventas_detalle une ventas con productos y sucursales (ver generar_datos.py).
-- El monitor vincula fechas ISO inclusivas y usa NULL para todas las opciones.
-- Los importes se agregan en centavos enteros antes de convertir a USD.

-- nombre: cobertura
SELECT MIN(fecha) AS inicio, MAX(fecha) AS fin, COUNT(*) AS registros
FROM ventas;

-- nombre: sucursales
SELECT sucursal_id, nombre, ciudad FROM sucursales ORDER BY nombre;

-- nombre: productos
SELECT producto_id, nombre, categoria FROM productos ORDER BY categoria, nombre;

-- nombre: kpi
-- Neto = unidades × precio tras descuento. Utilidad = neto − costo de venta.
SELECT COUNT(*) AS registros,
       COALESCE(SUM(unidades), 0) AS unidades,
       COALESCE(SUM(ingresos_centavos), 0) AS ingresos_centavos,
       COALESCE(SUM(utilidad_centavos), 0) AS utilidad_centavos,
       100.0 * SUM(utilidad_centavos) / NULLIF(SUM(ingresos_centavos), 0) AS margen_pct
FROM v_ventas_detalle
WHERE fecha BETWEEN :inicio AND :fin
  AND (:sucursal_id IS NULL OR sucursal_id = :sucursal_id)
  AND (:categoria IS NULL OR categoria = :categoria);

-- nombre: serie_diaria
-- El grano diario permite calcular una media móvil sin introducir días artificiales.
SELECT fecha, SUM(ingresos_centavos) AS ingresos_centavos
FROM v_ventas_detalle
WHERE fecha BETWEEN :inicio AND :fin
  AND (:sucursal_id IS NULL OR sucursal_id = :sucursal_id)
  AND (:categoria IS NULL OR categoria = :categoria)
GROUP BY fecha
ORDER BY fecha;

-- nombre: categorias
-- El cociente de sumas pondera el margen por los ingresos de cada línea.
SELECT categoria, SUM(unidades) AS unidades, SUM(ingresos_centavos) AS ingresos_centavos,
       SUM(utilidad_centavos) AS utilidad_centavos,
       100.0 * SUM(utilidad_centavos) / NULLIF(SUM(ingresos_centavos), 0) AS margen_pct
FROM v_ventas_detalle
WHERE fecha BETWEEN :inicio AND :fin
  AND (:sucursal_id IS NULL OR sucursal_id = :sucursal_id)
  AND (:categoria IS NULL OR categoria = :categoria)
GROUP BY categoria
ORDER BY ingresos_centavos DESC, categoria;

-- nombre: productos_top
SELECT producto, SUM(ingresos_centavos) AS ingresos_centavos, SUM(unidades) AS unidades
FROM v_ventas_detalle
WHERE fecha BETWEEN :inicio AND :fin
  AND (:sucursal_id IS NULL OR sucursal_id = :sucursal_id)
  AND (:categoria IS NULL OR categoria = :categoria)
GROUP BY producto_id, producto
ORDER BY ingresos_centavos DESC, producto
LIMIT 5;

-- nombre: detalle
-- LIMIT -1 entrega todas las filas. La vista previa solicita un límite explícito.
SELECT fecha, sucursal, ciudad, producto, categoria, unidades, descuento_pct,
       precio_lista_centavos, precio_neto_centavos, costo_unitario_centavos,
       ingresos_centavos, costo_venta_centavos, utilidad_centavos
FROM v_ventas_detalle
WHERE fecha BETWEEN :inicio AND :fin
  AND (:sucursal_id IS NULL OR sucursal_id = :sucursal_id)
  AND (:categoria IS NULL OR categoria = :categoria)
ORDER BY fecha DESC, sucursal_id, producto_id
LIMIT :limite;

-- nombre: entrenamiento
-- El precio relativo facilita comparar precios entre productos de distinto valor.
-- La disponibilidad de entradas se limita a lo conocido al configurar el escenario.
SELECT v.fecha, v.sucursal_id, v.producto_id, p.categoria, v.unidades, v.descuento_pct,
       1.0 * v.precio_lista_centavos / p.precio_referencia_centavos AS precio_relativo
FROM ventas AS v
JOIN productos AS p ON p.producto_id = v.producto_id
ORDER BY v.fecha, v.sucursal_id, v.producto_id;

-- nombre: precios_escenario
SELECT MIN(v.precio_lista_centavos) AS minimo,
       MAX(v.precio_lista_centavos) AS maximo,
       (SELECT precio_lista_centavos FROM ventas
        WHERE sucursal_id = :sucursal_id AND producto_id = :producto_id
        ORDER BY fecha DESC LIMIT 1) AS reciente,
       p.precio_referencia_centavos AS referencia
FROM ventas AS v
JOIN productos AS p ON p.producto_id = v.producto_id
WHERE v.sucursal_id = :sucursal_id AND v.producto_id = :producto_id
GROUP BY p.precio_referencia_centavos;
