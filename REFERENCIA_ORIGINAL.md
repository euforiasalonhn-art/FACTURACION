# FRY Chicken POS — Documentación completa del proyecto

**Nombre:** FRY Chicken POS  
**Tipo:** Punto de venta de escritorio para Windows  
**Versión documentada:** Prototipo de escritorio actual  
**Tecnologías:** Python, Flask, PySide6 / Qt WebEngine, HTML, CSS, JavaScript y SQLite  
**Moneda de operación:** Lempiras (L)

---

## 1. ¿Qué es FRY Chicken POS?

FRY Chicken POS es un prototipo de punto de venta (POS) para registrar ventas de un restaurante, seleccionar productos desde un catálogo, calcular importes e impuestos estimados, registrar pagos, generar un comprobante de venta y consultar reportes.

La versión de escritorio envuelve la interfaz del sistema en una ventana nativa de Windows. El motor local de la aplicación se ejecuta en la misma computadora y la información se guarda en una base de datos SQLite local.

### Objetivo operativo definido

- Una instalación independiente por computadora/punto de venta.
- La ventana se abre maximizada, pero se puede minimizar, restaurar y cerrar.
- La aplicación debe poder utilizarse sin conexión a Internet.
- Cada instalación conserva sus propios datos locales.
- Los números internos de factura se comparten entre las modalidades Normal y RTN dentro de cada punto de venta.
- Los reportes permiten consultar todas las facturas o filtrar Normal y RTN por separado.

**Importante:** el sistema actual es un prototipo operativo/técnico. No es un sistema fiscal certificado y sus comprobantes no deben presentarse como facturas fiscales autorizadas.

---

## 2. Tecnologías y función de cada una

| Tecnología | Función |
|---|---|
| Python 3.12 | Lenguaje principal y lógica de negocio |
| Flask | Servidor local y API interna |
| PySide6 | Ventana nativa de Windows |
| Qt WebEngine | Muestra la interfaz dentro de la ventana de escritorio |
| HTML | Estructura de las pantallas |
| CSS | Diseño, colores, distribución y estilos |
| JavaScript | Interacción, carrito, navegación y llamadas a la API |
| SQLite | Base de datos local en un archivo |
| PyInstaller | Empaqueta el programa para distribuirlo como aplicación Windows |

No se requiere que el empleado abra Chrome. El contenido web se muestra dentro de la ventana de escritorio mediante Qt WebEngine.

---

## 3. Estructura de carpetas y archivos

```text
fry_chicken_pos/
│
├── app.py
├── desktop_main.py
├── requirements.txt
├── requirements-desktop.txt
├── BUILD_EXE_WINDOWS.bat
├── README.md
├── README_DESKTOP.md
├── README_COMPLETO.md
│
├── templates/
│   └── index.html
│
└── static/
    ├── css/
    │   └── style.css
    │
    └── js/
        └── app.js
```

### 3.1 `app.py` — Núcleo del sistema

Contiene la aplicación Flask, conexión con SQLite, creación de tablas, catálogo inicial, reglas de cálculo y rutas de la API.

Responsabilidades actuales:

1. Determinar la carpeta de recursos y la carpeta de datos.
2. Crear/conectar la base SQLite.
3. Crear las tablas si todavía no existen.
4. Insertar una sucursal principal y un catálogo inicial si la base está vacía.
5. Consultar y crear puntos de venta.
6. Consultar, crear y actualizar productos.
7. Calcular subtotal, impuestos estimados, descuentos y total.
8. Registrar ventas y sus artículos.
9. Consultar detalles de facturas.
10. Consultar reportes y anular ventas de forma lógica.

### 3.2 `desktop_main.py` — Lanzador de escritorio

Es el punto de entrada de la versión Windows.

Responsabilidades:

1. Crear la carpeta local de datos del usuario.
2. Definir la variable `FRY_CHICKEN_DATA_DIR` antes de importar el núcleo.
3. Inicializar la base de datos.
4. Iniciar el servidor Flask en `127.0.0.1` y en un puerto local disponible.
5. Crear la ventana de PySide6.
6. Mostrar la interfaz dentro de `QWebEngineView`.
7. Abrir la ventana maximizada, conservando los controles normales de Windows.
8. Cerrar el servidor local al cerrar la ventana.

La dirección `127.0.0.1` significa que el servidor escucha solamente en la computadora local; no publica el sistema para otras computadoras de la red.

### 3.3 `templates/index.html` — Pantalla principal

Define la estructura de la interfaz:

- Barra lateral de navegación.
- Encabezado y selector de punto de venta.
- Vista de punto de venta.
- Catálogo y categorías.
- Carrito y detalle de la venta.
- Selección de factura Normal o RTN.
- Campos de cliente para RTN.
- Resumen de subtotal, impuestos estimados y total.
- Vista de reportes.
- Vista de productos y precios.
- Vista de puntos de venta.
- Ventana de cobro.
- Ventana de comprobante e impresión.

### 3.4 `static/css/style.css` — Diseño visual

Controla:

- Colores y tipografía.
- Distribución de la pantalla.
- Barra lateral y encabezado.
- Tarjetas de productos.
- Botones y campos.
- Catálogo y carrito.
- Tablas y tarjetas de reportes.
- Ventanas modales.
- Diseño adaptable al tamaño de la ventana.
- Estilos de impresión del comprobante.

### 3.5 `static/js/app.js` — Interacción de la interfaz

Controla:

- Navegación entre módulos.
- Búsqueda y filtrado visual de productos.
- Renderizado de categorías y productos.
- Agregar productos al carrito.
- Aumentar y disminuir cantidades.
- Vaciar el pedido.
- Cambiar entre Normal y RTN.
- Abrir el diálogo de cobro.
- Calcular visualmente el cambio.
- Enviar la venta al servidor.
- Mostrar el comprobante.
- Consultar reportes.
- Exportar reportes CSV.
- Crear sucursales/puntos de venta.
- Crear productos y actualizar precios/clasificación fiscal.

### 3.6 `requirements.txt`

Dependencias del núcleo web inicial. Actualmente incluye Flask.

### 3.7 `requirements-desktop.txt`

Dependencias para ejecutar y empaquetar la aplicación de escritorio: Flask, PySide6 y PyInstaller.

### 3.8 `BUILD_EXE_WINDOWS.bat`

Script de Windows que:

1. Verifica Python 3.12.
2. Crea el entorno virtual `.venv` si no existe.
3. Activa el entorno.
4. Actualiza pip.
5. Instala las dependencias de escritorio.
6. Ejecuta PyInstaller en modo `onedir`.
7. Incluye las carpetas `templates` y `static`.
8. Genera la carpeta `dist\FRYChickenPOS`.

La compilación del EXE debe ejecutarse en Windows. El resultado es una carpeta distribuible; no se debe copiar únicamente el EXE porque necesita los archivos de soporte generados por PyInstaller.

---

## 4. Módulos visibles de la aplicación

### 4.1 Punto de venta

Es la pantalla principal para registrar una compra.

Permite actualmente:

1. Seleccionar el punto de venta activo en el selector superior.
2. Buscar productos por nombre.
3. Filtrar productos por categoría.
4. Agregar productos al carrito.
5. Aumentar o disminuir la cantidad de cada artículo.
6. Quitar una línea al reducir su cantidad a cero.
7. Vaciar todo el pedido con confirmación.
8. Elegir el tipo de comprobante: Normal o RTN.
9. Introducir nombre/razón social y RTN cuando se selecciona RTN.
10. Introducir un descuento en lempiras.
11. Revisar subtotal, impuestos estimados y total.
12. Continuar al cobro.

El catálogo inicial se basa en las categorías y nombres de productos visibles en las fotografías proporcionadas del sistema anterior. Los precios se inicializan en L 0.00 y deben configurarse antes de realizar pruebas de venta.

### 4.2 Tipos de factura

La interfaz permite elegir:

**Factura Normal**
- Se identifica como `NORMAL`.
- Utiliza por defecto el nombre `CONSUMIDOR FINAL` si no se proporciona otro nombre.
- No muestra los campos de RTN en la pantalla de venta.

**Factura con RTN**
- Se identifica como `RTN`.
- Muestra campos para nombre/razón social y RTN del cliente.
- Guarda esos datos en el registro de la venta.

**Numeración actual**
- Cada punto de venta tiene un contador `next_invoice`.
- Las modalidades NORMAL y RTN consumen el mismo contador de ese punto de venta.
- Ejemplo ilustrativo: Normal 17, RTN 18, Normal 19.
- El número se asigna al guardar/confirmar la venta, no al seleccionar productos.
- La base de datos impide repetir el mismo número dentro del mismo punto de venta mediante una restricción única.

Esta numeración es interna del prototipo. No equivale a un correlativo fiscal autorizado por el SAR.

### 4.3 Cobro

Al pulsar “Continuar al cobro” se abre una ventana con:

- Total a pagar.
- Forma de pago.
- Importe recibido.
- Cambio calculado.

Formas de pago disponibles actualmente:

- Efectivo.
- Tarjeta.
- Transferencia.
- Otro.

Al confirmar, el sistema registra la venta y muestra el comprobante.

**Limitación actual:** no hay integración con terminal bancaria, pasarela de pago ni conciliación automática. El método de pago es un dato registrado por el operador.

### 4.4 Comprobante e impresión

Después de guardar la venta se muestra un comprobante con:

- Nombre del restaurante.
- Punto de venta.
- Dirección configurada.
- Número interno de factura.
- Modalidad Normal o RTN.
- Fecha y hora.
- Nombre del cliente y RTN si aplica.
- Detalle de productos, cantidades y precios.
- Subtotal.
- ISV estimado al 15%.
- ISV estimado al 18%.
- Descuento.
- Total.
- Forma de pago.
- Importe recibido.
- Cambio.

El botón “Imprimir” utiliza la función de impresión del contenido mostrado por el motor web.

**Limitación actual:** es una impresión de comprobante de prueba. Todavía no se ha configurado ni probado una impresora térmica específica, ancho de papel, corte automático, cajón de dinero ni formato fiscal definitivo.

### 4.5 Reportes

La pantalla de reportes permite:

- Consultar todas las facturas.
- Filtrar solamente facturas normales.
- Filtrar solamente facturas con RTN.
- Establecer fecha inicial y fecha final.
- Ver número de factura.
- Ver fecha.
- Ver tipo.
- Ver cliente.
- Ver RTN.
- Ver estado.
- Ver total.
- Consultar el total de facturas normales.
- Consultar el total de facturas RTN.
- Consultar la suma de ventas emitidas.
- Exportar el resultado consultado a CSV.

El listado conserva el número interno original y se ordena por el número consecutivo. Filtrar RTN no renumera las facturas: muestra los números que realmente tuvieron esas ventas.

El CSV se puede abrir con Excel u otras hojas de cálculo.

### 4.6 Productos y precios

La pantalla permite:

- Agregar un producto.
- Escribir nombre.
- Asignar categoría.
- Definir precio en lempiras.
- Asignar clasificación fiscal de ejemplo.
- Actualizar el precio de un producto existente.
- Actualizar la clasificación fiscal.

Clasificaciones disponibles en el prototipo:

- Gravado 15%.
- Gravado 18%.
- Exento.
- Exonerado.

No se debe asumir que estas opciones o porcentajes son correctos para todos los productos. La clasificación y el tratamiento fiscal deben validarse con el contador y la normativa aplicable.

### 4.7 Sucursales / puntos de venta

La pantalla permite crear puntos de venta con:

- Nombre.
- Dirección.
- RTN del emisor (campo opcional).
- Número inicial para la secuencia interna.

Cada punto de venta creado tiene su propio identificador y contador `next_invoice` dentro de esa base de datos.

**Importante para el despliegue solicitado:** el diseño acordado es una computadora independiente por punto de venta. Si se instala una copia en cada computadora, cada instalación tendrá su propia base de datos. Crear un punto de venta dentro de una instalación no sincroniza automáticamente esa información con otra computadora.

---

## 5. Catálogo inicial

El catálogo se crea automáticamente cuando la tabla de productos está vacía.

Categorías incluidas:

1. Personales sin refresco.
2. Refrescos.
3. Familiares.
4. Complementos.
5. Promociones.
6. Pollo entero/piezas.
7. Arroz chino.
8. Pollo asado.
9. Económicos.
10. Envíos a domicilio.
11. Menú empleados.

Los nombres de los productos iniciales están definidos en la lista `SEED` dentro de `app.py`.

Los productos iniciales no tienen fotografías individuales asociadas en la base de datos. La interfaz usa iconos/emojis por categoría como representación visual. Los precios iniciales son cero.

---

## 6. Cálculos de venta actuales

La función `calculate()` procesa las líneas del carrito.

Para cada producto:

1. Multiplica cantidad por precio unitario.
2. Clasifica el importe según el tipo fiscal configurado.
3. Suma el importe a la base correspondiente.
4. Calcula el impuesto de ejemplo cuando aplica.

Tratamiento programado actualmente:

- `EXENTO`: se suma al importe exento.
- `EXONERADO`: se suma al importe exonerado.
- `15`: calcula 15% sobre la línea.
- `18`: calcula 18% sobre la línea.

Fórmula implementada:

`Total = Subtotal + ISV 15% + ISV 18% - Descuento`

El descuento se limita para que no sea menor que cero ni mayor que el subtotal.

**Supuesto importante:** el prototipo trata los precios introducidos como precios antes de impuesto y agrega el impuesto al total. Si el menú de FRY Chicken utiliza precios finales con impuesto incluido, la fórmula deberá modificarse antes de operar.

Los cálculos actuales son estimados de prototipo; requieren revisión contable/fiscal.

---

## 7. Base de datos SQLite

### 7.1 Ubicación

En la versión de escritorio, el archivo de base de datos se guarda en:

```text
%LOCALAPPDATA%\FRYChickenPOS\data\fry_chicken.db
```

Ejemplo habitual:

```text
C:\Users\<usuario>\AppData\Local\FRYChickenPOS\data\fry_chicken.db
```

La base de datos está fuera de la carpeta del EXE para evitar que una actualización del programa la sobrescriba.

### 7.2 Tablas actuales

#### `branches`

Almacena los puntos de venta.

Campos principales:

- `id`: identificador.
- `name`: nombre.
- `address`: dirección.
- `rtn`: RTN del emisor.
- `next_invoice`: siguiente número interno.
- `active`: estado activo.
- `created_at`: fecha de creación.

#### `products`

Almacena el catálogo.

Campos principales:

- `id`: identificador.
- `category`: categoría.
- `name`: nombre del producto.
- `price`: precio.
- `tax_type`: clasificación fiscal configurada.
- `active`: estado activo.

#### `invoices`

Almacena la cabecera de cada venta.

Campos principales:

- `id`: identificador interno de la fila.
- `branch_id`: punto de venta.
- `number`: número interno de factura.
- `invoice_type`: `NORMAL` o `RTN`.
- `customer_name`: nombre del cliente.
- `customer_rtn`: RTN del cliente.
- `payment_method`: forma de pago.
- `amount_received`: importe recibido.
- `subtotal`: subtotal.
- `exempt`: importe exento.
- `exempted`: importe exonerado.
- `taxable_15`: base gravada al 15%.
- `tax_15`: impuesto calculado al 15%.
- `taxable_18`: base gravada al 18%.
- `tax_18`: impuesto calculado al 18%.
- `discount`: descuento.
- `total`: total.
- `created_at`: fecha y hora.
- `status`: estado, inicialmente `EMITIDA`.

La combinación `branch_id` + `number` tiene una restricción de unicidad.

#### `invoice_items`

Almacena el detalle de productos de cada factura.

Campos principales:

- `id`: identificador.
- `invoice_id`: factura relacionada.
- `product_id`: producto relacionado cuando existe.
- `product_name`: nombre guardado en la venta.
- `quantity`: cantidad.
- `unit_price`: precio unitario guardado.
- `tax_type`: clasificación fiscal guardada.
- `line_total`: total de la línea.

Guardar el nombre, precio y clasificación dentro del detalle permite conservar la información histórica de la venta aunque el catálogo cambie posteriormente.

---

## 8. API interna actual

La API se utiliza internamente entre JavaScript y Flask. No está pensada como API pública de Internet.

| Método | Ruta | Función |
|---|---|---|
| GET | `/` | Carga la pantalla principal |
| GET | `/api/branches` | Consulta puntos de venta activos |
| POST | `/api/branches` | Crea un punto de venta |
| GET | `/api/products` | Consulta productos activos |
| POST | `/api/products` | Crea un producto |
| PATCH | `/api/products/<id>` | Actualiza precio/clasificación de un producto |
| POST | `/api/invoices` | Registra una venta |
| GET | `/api/reports` | Consulta reportes con filtros |
| GET | `/api/invoices/<id>` | Consulta detalle de una factura |
| POST | `/api/invoices/<id>/void` | Marca una factura como anulada |

---

## 9. Funcionamiento sin Internet

La versión de escritorio está diseñada para operar localmente:

1. La ventana se ejecuta en la computadora.
2. Flask escucha en la dirección local `127.0.0.1`.
3. HTML, CSS y JavaScript se cargan desde los archivos incluidos en el paquete.
4. La base de datos SQLite está en el disco local.
5. Las operaciones de venta y consulta no necesitan un servidor externo.
6. La interfaz usa fuentes disponibles en Windows y no necesita descargar fuentes web.

Por ello, el flujo local de venta puede funcionar sin Internet una vez que el programa y sus dependencias estén instalados.

**La ausencia de Internet no equivale a un sistema sincronizado:** las computadoras independientes no comparten ventas ni reportes automáticamente.

---

## 10. Instalación y ejecución en modo desarrollo

Requisitos recomendados para esta versión:

- Windows 10 u 11 de 64 bits.
- Python 3.12 de 64 bits para ejecutar el proyecto desde el código.
- Conexión a Internet durante la primera instalación de dependencias, salvo que se disponga de paquetes previamente descargados.

Desde CMD, dentro de la carpeta del proyecto:

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements-desktop.txt
python desktop_main.py
```

Para cerrar, se utiliza el botón de cerrar de la ventana.

---

## 11. Crear la versión EXE

En Windows:

1. Instalar Python 3.12 de 64 bits.
2. Descomprimir el proyecto.
3. Ejecutar `BUILD_EXE_WINDOWS.bat`.
4. Esperar que PyInstaller termine.
5. Revisar la carpeta `dist\FRYChickenPOS`.

El archivo principal se genera en:

```text
dist\FRYChickenPOS\FRYChickenPOS.exe
```

Se debe distribuir la carpeta completa `FRYChickenPOS`, no solamente el EXE.

La compilación necesita descargar las dependencias la primera vez. Después de compilar, el programa empaquetado está pensado para ejecutarse localmente sin que el equipo tenga Python instalado.

---

## 12. Respaldo y recuperación de datos

### Respaldo manual

1. Cerrar FRY Chicken POS.
2. Abrir el Explorador de archivos.
3. Pegar esta ruta en la barra de direcciones:

```text
%LOCALAPPDATA%\FRYChickenPOS\data\
```

4. Copiar `fry_chicken.db`.
5. Guardar una copia en una memoria USB o ubicación segura.

### Restauración manual

1. Cerrar el programa.
2. Abrir la misma carpeta de datos.
3. Conservar una copia del archivo actual por seguridad.
4. Sustituir `fry_chicken.db` por el respaldo.
5. Abrir el programa y comprobar la información.

No se ha implementado todavía un asistente automático de copias ni restauración.

---

## 13. Qué está implementado y qué falta

### Implementado en el prototipo actual

- [x] Ventana de escritorio PySide6.
- [x] Ventana maximizada y minimizable.
- [x] Servidor interno local.
- [x] Recursos HTML/CSS/JavaScript locales.
- [x] Base de datos SQLite.
- [x] Catálogo inicial por categorías.
- [x] Búsqueda de productos.
- [x] Carrito de compra.
- [x] Cantidades y eliminación de líneas.
- [x] Modalidad Normal y RTN.
- [x] Campos de cliente y RTN.
- [x] Descuento.
- [x] Cálculo estimado de impuestos.
- [x] Registro de forma de pago e importe recibido.
- [x] Cálculo de cambio.
- [x] Comprobante de prueba e impresión del navegador integrado.
- [x] Reportes por tipo y fechas.
- [x] Exportación CSV.
- [x] Creación de puntos de venta.
- [x] Creación y actualización de productos.
- [x] Anulación lógica de factura sin reutilizar su número.

### Pendiente para una versión de producción

- [ ] Integración fiscal y validación de requisitos vigentes del SAR.
- [ ] CAI, rango autorizado, fecha límite y controles de correlativos fiscales.
- [ ] Configuración completa de establecimiento y punto de emisión.
- [ ] Validación de RTN y datos fiscales del emisor/cliente.
- [ ] Desglose fiscal definitivo conforme a cada producto y operación.
- [ ] Diseño final de factura fiscal y comprobante.
- [ ] Pruebas con la impresora térmica real y papel utilizado.
- [ ] Control de caja: apertura, retiros, ingresos y cierre.
- [ ] Usuarios, contraseñas, roles y permisos.
- [ ] Registro de auditoría de operaciones.
- [ ] Gestión de inventario y existencias.
- [ ] Comandas y envío de pedidos a cocina.
- [ ] Devoluciones y políticas de anulación autorizadas.
- [ ] Respaldo automático y restauración guiada.
- [ ] Pruebas de recuperación ante apagones y cierres inesperados.
- [ ] Protección de la base de datos y controles de acceso.
- [ ] Sincronización entre sucursales, si en el futuro se solicita.
- [ ] Pruebas de aceptación con empleados y encargados.

---

## 14. Consideraciones de seguridad y operación

1. No borrar manualmente facturas de la base de datos.
2. No copiar una base de datos de una sucursal sobre otra sin un procedimiento de migración.
3. Realizar respaldos frecuentes.
4. Restringir el acceso de Windows a la carpeta de datos.
5. No usar precios en cero ni clasificaciones fiscales de ejemplo para ventas reales.
6. Probar la impresión antes de abrir el negocio.
7. No considerar el número interno como autorización fiscal.
8. No emitir documentos fiscales reales con este prototipo.
9. Mantener el EXE y la base de datos como elementos separados.
10. Probar cada actualización con una copia de seguridad antes de instalarla en la computadora de caja.

---

## 15. Glosario

- **POS:** punto de venta.
- **RTN:** Registro Tributario Nacional.
- **ISV:** Impuesto Sobre Ventas.
- **CAI:** Código de Autorización de Impresión.
- **Correlativo interno:** número secuencial asignado por el prototipo.
- **SQLite:** base de datos local almacenada en un archivo.
- **PyInstaller:** herramienta que empaqueta una aplicación Python.
- **PySide6:** biblioteca para crear ventanas de escritorio.
- **CSV:** archivo de datos tabulares que puede abrirse con Excel.

---

## 16. Resumen ejecutivo

FRY Chicken POS es actualmente un prototipo de escritorio local para Windows que permite seleccionar productos, armar una venta, registrar pago, guardar una factura interna, imprimir un comprobante de prueba y consultar reportes.

La arquitectura usa Python y Flask para la lógica y API local, PySide6 para la ventana de Windows, HTML/CSS/JavaScript para la interfaz y SQLite para guardar los datos de cada instalación.

El diseño objetivo acordado es una computadora independiente por punto de venta, con ventana maximizada y minimizable y operación sin Internet. Para convertirse en el sistema definitivo del restaurante todavía requiere completar la integración fiscal, seguridad, caja, inventario, impresión validada y pruebas de operación real.
