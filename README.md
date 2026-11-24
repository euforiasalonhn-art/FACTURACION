# Versión actual V54 — Cabecera del contador corregida

Lee LEEME-V54.txt.

# Versión actual V53 — Envío de L 30 a L 200, de 5 en 5

Lee LEEME-V53.txt.

# Versión actual V52 — Foto hasta los bordes laterales

Lee LEEME-V52.txt.

# Versión actual V51 — Fotos más grandes y precio destacado

Lee LEEME-V51.txt.

# Versión actual V50 — Contraste de modo claro y oscuro

Lee LEEME-V50.txt.

# Versión actual V49 — Bienvenida del empleado sobre el catálogo

Lee LEEME-V49.txt.

# Versión actual V48 — Corrección del arranque duplicado en Windows

Lee LEEME-V48.txt.

# Versión actual V47 — Ingreso en dos pasos por sucursal

Lee LEEME-V47.txt. Primero contraseña de sucursal, después código de empleado.

# Versión actual V46 — Pantalla compacta y empresas exentas / exoneradas

Lee LEEME-V46.txt para configurar empresas, productos autorizados y atajos.

# Versión actual V45 — Notas junto a las categorías

Lee LEEME-V45-NOTAS.txt para este cambio visual y LEEME-V44-MULTICAJA.txt para configurar MÁQUINA 1 y las terminales.

Versión 21: en la factura, Precio y Total de cada producto se presentan sin ISV. Si el precio del menú incluye impuesto, se separa usando la tasa guardada del producto (15 % o 18 %); exentos y precios configurados antes de ISV se conservan sin volver a dividir.

Ejemplo verificado: dos productos de L 50 con ISV 15 % incluido muestran precio unitario L 43.48 y total de línea L 86.96. El resumen mantiene base L 86.96, ISV L 13.04 y total a pagar L 100.00. El precio del menú y los importes cobrados guardados no se modifican. La presentación se calcula desde el snapshot de cada factura.

Se conservan la precisión interna y los ajustes de centavos por grupo al mostrar los importes de las líneas; en cantidades o combinaciones que generen fracciones de centavo, el total de línea se obtiene antes de redondear y puede diferir un centavo del producto del precio unitario ya redondeado por la cantidad. Los descuentos continúan mostrándose en el resumen; los valores de los productos se presentan antes del descuento.

Pruebas: ejemplo 50 × 2 completo guardado y renderizado; impuesto 18 %, exentos, precios exclusivos, distribución de redondeo y conservación del snapshot. PDF revisado en 80 y 58 mm con los cuatro valores del ejemplo.

Versión 20: formato de factura basado en la referencia fotográfica. Se ajusta únicamente el comprobante y su vista previa: sin logo, encabezado compacto centrado, tipografía Arial en tamaño térmico, rango inicial/final en una fila, cajero y orden en paralelo, cliente y RTN, tabla Cantidad/Descripción/Precio/Total, importes e impuestos agrupados, total en letras, pago a dos columnas y leyendas de cierre.

En efectivo, el comprobante muestra el dinero físico recibido y el cambio; el reporte mantiene el efectivo aplicado como importe de venta. Transferencia aparece cuando corresponde. La configuración de emisor, CAI, rango y numeración se obtiene de la sucursal; no se copian datos ni autorizaciones de la foto. Para completarlos usa Facturación y CAI. Sin autorización configurada, el comprobante conserva su identificación de muestra.

La vista previa ocupa el ancho de un ticket en vez de estirarse en toda la ventana. La salida de escritorio conserva selección de papel 58/80 mm y longitud automática. Se generaron y revisaron PDF de ambos anchos, con una compra de un artículo y otra de 40 artículos. Los datos de las vistas de ejemplo son ficticios y se identifican como MUESTRA DE DISEÑO. No se envió impresión física.

Versión 19: cobro con textos en negrita, números y botones más grandes. El aplicado, pendiente y cambio se actualizan al salir de cada campo o al avanzar con Enter/Tab; no mientras se escribe. En pago mixto, el efectivo recibido se inicia según el efectivo aplicado y no con el total de la compra. Puedes modificarlo si el cliente entrega más dinero; el cambio corresponde únicamente al efectivo.

Se corrigió la compatibilidad con la base anterior: se agregan las columnas de detalle histórico de la venta y clave para evitar duplicados que faltaban y se guardan todos los campos fiscales que la base requiere. Antes de migrar se crea respaldo-antes-v19-FECHA-HORA.db en la carpeta de datos. Se conservan los registros anteriores y no se inventan detalles de facturas históricas que no los tengan.

Pruebas realizadas sobre una copia aislada de la base existente: pago mixto de L 9,380 con efectivo L 1,000, transferencia L 1,073 y tarjeta L 7,307, efectivo recibido L 1,000 y cambio cero; reintento sin duplicar; factura RTN, reporte contable y respaldo. También se verificó en la interfaz que escribir no cambie el pendiente hasta salir del campo y que los importes se presenten con el nuevo tamaño. No se modificó la base original durante las pruebas.

Versión 18: descuento, porcentaje y tipo de cliente se ubican en la fila del buscador, fuera del panel de compra. La búsqueda es más compacta. El cliente sin RTN se identifica y guarda siempre como CONSUMIDOR FINAL; los clientes con RTN conservan su nombre o razón social.

La hora visible usa formato de 12 horas con a. m./p. m. La lista de compra tiene desplazamiento vertical propio y mantiene total y cobro visibles. El catálogo también se desplaza por separado. Se verificó con 12 líneas de compra en ventanas de 1600 × 950 y 1280 × 720, además del guardado de consumidor final en la factura y las pruebas de ventas, descuentos, permisos y caja.

Versión 17: aviso de caja abierta más compacto, con datos separados y fecha/hora legibles de Honduras. Reloj, logo y sucursal centrados sobre el panel de compra; menú en la esquina derecha. Se oculta el texto de validación, manteniendo la comprobación NTP en segundo plano.

# Pantalla completa y hora de Honduras — versión 16

Abre INICIAR.bat. La aplicación de escritorio inicia en pantalla completa, cubriendo también la barra de tareas de Windows. F11 permite alternar con ventana normal cuando necesites salir de pantalla completa.

Encima del logo se muestran fecha y hora con segundos en horario America/Tegucigalpa. La fuente es el reloj de la PC. Un proceso independiente consulta time.google.com por NTP (UDP 123) al inicio y cada quince minutos. Si falla, reintenta cada minuto sin detener las ventas. Google documenta ese servidor público en https://developers.google.com/time.

La pantalla indica HORA VALIDADA CON GOOGLE cuando la diferencia medida es de cinco segundos o menos. Si supera ese margen muestra REVISAR RELOJ DE LA PC; en el indicador se puede consultar la diferencia. Si no hay respuesta o el reloj de la PC cambió después de la comprobación, muestra SIN VALIDAR hasta la siguiente comprobación. El programa no modifica la hora ni la configuración de Windows. Para que la comprobación funcione, la conexión debe permitir NTP hacia el servidor de Google.

Se verificó respuesta real del servidor Google, procesamiento NTP con validación de respuesta y cambio de era, detección de cambios del reloj, pantalla completa/F11 y la presentación de fecha y hora. La vista previa usa datos de demostración y muestra SIN VALIDAR.

# Complemento de productos existentes V14 — versión 15

Esta actualización NO incorpora los 105 productos del catálogo antiguo. Solo busca coincidencias en los productos que ya existen en la aplicación. No crea productos, no renombra ninguno y no cambia sus categorías. Completa únicamente precios cero y fotos ausentes. Los datos asignados por el administrador se conservan.

Se recuperaron fotos para 67 de los 81 productos visibles actuales y 11 precios verificables para la presentación correspondiente. Los precios proceden de los carteles de combos/promociones incluidos y de tres artículos exactos de la copia SQLite. Son precios del archivo, sin confirmación de vigencia. Los carteles que incluyen refresco no se usan como precio de presentaciones sin refresco.

Abre REVISION_PRODUCTOS_V14.html para revisar producto por producto la imagen, el precio y la fuente. Los campos sin respaldo se dejan pendientes; no se inventan precios ni se asignan fotos de otro producto. Las categorías de domicilio y menú empleados que ya estaban ocultas quedan fuera.

Descomprime y abre INICIAR.bat. Antes de completar los productos se crea un respaldo de la base en la carpeta de datos, con nombre respaldo-antes-catalogo-v15-FECHA-HORA.db. La actualización se aplica una vez por producto para respetar cambios posteriores.

Versión 14: apertura de caja en mayúsculas, título centrado, logo a la derecha y nombre de sucursal con prefijo SUCURSAL y mayor grosor.

Versión 13: ventana de inicio de caja ampliada, números grandes, botones amplios y todos sus textos en negrita.

# Caja y menú de sesión — versión 12

Abre INICIAR.bat. Al ingresar a sucursal aparece Iniciar caja para registrar el fondo inicial. Si ya hay una caja abierta, aparece Continuar caja abierta: no se duplica la apertura ni se reemplaza el fondo inicial.

El botón de hamburguesa arriba a la derecha ofrece Cerrar caja y Cerrar sesión. Cerrar sesión conserva abierta la caja para continuar al ingresar otra vez. Cerrar caja pide el efectivo contado, muestra esperado y diferencia, y guarda el cierre definitivo con responsable y fechas. Antes hay que finalizar o vaciar la compra pendiente. Después puedes descargar el PDF del cierre y abrirlo para imprimir, cerrar sesión o iniciar una nueva caja.

Esperado = fondo inicial + ventas en efectivo + ingresos de caja - egresos de caja. Tarjeta y transferencia se muestran aparte. Los consumos especiales sin cobro aparecen con cantidad y valor de referencia, sin sumar efectivo ni ventas cobradas. Nuevas ventas y registros especiales requieren caja abierta en el servidor. No se reasignan ventas ni consumos históricos a una caja nueva.

Se revisó la apertura y cierre del programa anterior en el archivo proporcionado: registra fondo inicial, resume pagos, compara contado/esperado, guarda diferencia y genera impresión. La nueva versión conserva esa operativa con importes en centavos, cierre transaccional y control del turno que se está cerrando. La apertura y cierre no reinician ni retroceden la numeración de facturas. No se importan productos ni datos de la instalación anterior.

Pruebas en base aislada: caja única por sucursal, reanudación después de cerrar sesión, cálculo de faltante, ventas/sin cobro vinculados, exportación PDF y bloqueo de operaciones sin caja o sobre otro turno/sucursal. Se revisó visualmente la apertura; no se envió impresión física.

El nombre de la sucursal aparece centrado debajo del logo. Las categorías aprovechan todo el espacio izquierdo de la cabecera y todos sus botones tienen el mismo ancho y alto, con letra más grande y en negrita.

# Orden de categorías y nueva distribución — versión 11

Abre INICIAR.bat. Entra como administrador y ve a Configuración > Orden de las categorías. Usa Subir/Bajar y luego Guardar orden. Sucursal solo consulta ese orden; no puede modificarlo. Se conserva al cerrar el programa. Las sucursales de otra computadora no se sincronizan automáticamente.

Las categorías ahora aparecen en la cabecera, los productos debajo del buscador ocupan el área de catálogo y el logo queda arriba junto al área de cobro. Los productos de cada categoría siguen ordenados alfabéticamente.

# FRY Chicken POS — Actualización especial de contabilidad, versión 11


## Cambios de la versión 9
El encabezado de venta muestra la sucursal. Se oculta el aviso superior de modo muestra en la pantalla, y se mantienen las marcas de muestra en los comprobantes que no tengan CAI. El menú de venta ya no muestra Todas las categorías, Envíos a domicilio ni Menú empleados. El catálogo histórico no se elimina.

Todos los descuentos de nuevas ventas son porcentuales. En Configuración, el administrador fija empleados y tercera edad. Sucursal elige Sin descuento, Empleados o Tercera edad; el servidor aplica el porcentaje guardado y no permite sustituirlo con otro importe.

## Registro especial para dueño o ejecutivo
En Configuración, completa Descuentos y registro especial: habilita la opción, registra el destinatario y la cuenta SMTP de envío (servidor, puerto 587 o 465, remitente, usuario y contraseña de aplicación si tu proveedor la requiere). La contraseña se conserva protegida por Windows en esta computadora; al mover la base a otra PC debes volver a ingresarla. El programa necesita conexión a Internet para enviar.

Sucursal verá una casilla de registro especial y un campo para el nombre del beneficiario. Al marcarla, la compra se guarda con sus productos, precios e importe de referencia, cobro cero y comprobante interno. No se asigna como pago efectivo ni se suma a ventas cobradas, no consume un correlativo CAI y no altera los porcentajes configurados. El registro conserva el desglose de referencia calculado, sin convertirlo automáticamente en una declaración de impuestos o un asiento de contabilidad general.

Cada registro intenta enviar un PDF al destinatario configurado en ese momento. Si falla, queda PENDIENTE en la base. Con el programa abierto se reintenta cada cinco minutos. Administrador también puede reenviar pendientes desde Contabilidad > Registro especial sin cobro. Administrador y contador consultan el total de consumos y exportan PDF y Excel, incluyendo productos. Para imprimir abre el PDF exportado y usa la opción Imprimir de tu lector de PDF. Estos consumos tienen su propio reporte, separado del libro de facturas cobradas.

El correo se verificó con un servidor simulado; debes completar la cuenta real para comprobar la entrega a tu destinatario. No se envió ningún correo real durante el desarrollo. Se comprobó precio antiguo de tipo REAL, descuento autorizado, permisos, duplicados, persistencia ante fallo de correo, factura cobrada y exportaciones.

## Instalar sin compilar
Cierra la versión anterior. Descomprime esta carpeta y abre INICIAR.bat. Necesitas Python 3.12 de 64 bits e Internet durante la instalación inicial de las dependencias. Después el programa opera localmente. No se requiere Internet para consultar o exportar.

También puedes ejecutar en CMD:

    python -m venv .venv
    .venv\Scripts\activate
    python -m pip install -r requirements-desktop.txt
    python desktop_main.py

Usa desktop_main.py o INICIAR.bat para disponer del guardado de descargas y del reporte de impresión integrado. app.py por separado abre la versión web local, cuyos archivos se descargan con el navegador.

## Conservación de datos
No importa ningún producto, precio, imagen, cliente o venta del sistema anterior analizado. Conserva el catálogo y los datos ya existentes en nuestra aplicación. La base sigue en:

    %LOCALAPPDATA%\FRYChickenPOS\data\fry_chicken.db

Antes de migrar una base anterior crea respaldo-antes-v7-FECHA-HORA.db en esa misma carpeta. Conserva también una copia propia con el programa cerrado. No se incluye una base vacía para reemplazar datos.

## Perfiles de sucursal
1. Ingresa como administrador y abre Puntos de venta. Las instalaciones nuevas no traen una sucursal ficticia precreada.
2. Crea cada perfil con nombre de sucursal y contraseña (mínimo 4 caracteres); los campos de dirección, RTN y correlativo son datos de apoyo.
3. Para cambiar la contraseña, usa el botón de esa sucursal en la lista. El cambio cierra las sesiones activas de ese perfil. Las sucursales sin ventas, turnos ni CAI activo se pueden retirar; sus datos se conservan y pueden restaurarse.
4. En el acceso inicial, el personal selecciona el nombre de su sucursal e ingresa su contraseña, sin correo.
5. La sucursal y el administrador ven las categorías al lado izquierdo y los productos alfabéticos a la derecha. El personal de sucursal no ve el menú administrativo. La aplicación incluye el logo adjunto, redondo y sin recortar el dibujo.

Si aparece una sucursal de una versión anterior que no vas a utilizar, el administrador puede retirarla si aún no tiene facturas, turnos ni CAI activo; se oculta del inicio y los datos quedan conservados. Los perfiles dan acceso a sucursales de esta misma instalación. No replican ventas ni productos en otras computadoras. En bases antiguas, la contraseña local que ya estaba guardada se conserva como contraseña del perfil principal durante la migración.

La creación de perfiles registra también fecha de alta y estado de la sucursal, incluso al actualizar una base de datos anterior que exige esos campos. El acceso de sucursal valida el nombre y su propia contraseña; no requiere guardar primero la configuración inicial del administrador.

## Crear el acceso del contador
1. Ingresa como administrador mediante la tuerca. Acceso inicial, si no lo cambiaste: frychickencompany@gmail.com / FRY2026.
2. Abre Configuración y busca Accesos del contador.
3. Ingresa el correo y una contraseña temporal de al menos 8 caracteres, y pulsa Crear cuenta.
4. Entrega esos datos al contador por tu medio habitual. El programa no envía correos.
5. El contador elige Ingresar como contador en el inicio, introduce correo y contraseña, y cambia la temporal antes de poder consultar datos.
6. Después puede cambiarla en Mi contraseña. Debe conocer la actual y repetir la nueva.
7. El administrador puede desactivar/reactivar la cuenta o restablecer su contraseña temporal. Esto invalida las sesiones anteriores; un restablecimiento obliga a cambiarla otra vez.

Las contraseñas se almacenan con hash. Los registros de auditoría y los reportes no contienen contraseñas. El control se aplica en el servidor, además de ocultar botones en pantalla. No hay cuenta ni contraseña predeterminada para contador: la crea el administrador. Se pueden crear varias cuentas.

## Permisos del contador
Puede consultar, exportar e imprimir todos los datos contables disponibles en esta instalación: libro de ventas, datos de facturas y clientes RTN, autorizaciones configuradas y datos históricos de CAI, bases exentas/exoneradas y gravadas, ISV 15/18, descuentos, pagos, anulaciones con motivo/responsable/fecha, turnos, movimientos y auditoría registrada desde esta versión.

No puede vender, modificar productos/precios/clientes, cambiar CAI o correlativos, crear accesos, abrir/cerrar caja, registrar movimientos ni anular facturas. Su única modificación permitida es cambiar su propia contraseña.

La cuenta es local a esta base de datos. No proporciona acceso remoto por correo ni sincroniza computadoras. Todas las sucursales significa las que están registradas en esta instalación. No incluye bases MySQL ni ventas de otros sistemas o equipos.

## Contabilidad, filtros y exportación
Disponible para administrador y contador. Puede elegir una o todas las sucursales, fechas, modalidad Normal/RTN, estado y medio de pago.
El filtro inicial es Solo fiscales con CAI. Puedes incluir o consultar por separado los documentos internos/muestras. Las muestras no deben sumarse por error al libro fiscal.

Los importes originales permanecen visibles en las anuladas, pero el resumen suma únicamente EMITIDAS. Cada factura se suma una vez. Los descuentos no se repiten por cada artículo. El filtro de medio de pago selecciona facturas que contienen ese medio; se muestran los importes completos de esas facturas y su distribución por medio.

- PDF completo: resumen, operaciones con detalle fiscal e histórico, autorizaciones actuales, turnos, movimientos, auditoría y clientes RTN. Papel A4 horizontal.
- Excel real .xlsx: hojas Resumen, Autorizaciones, Libro de ventas, Detalle histórico, Turnos, Movimientos de caja, Auditoría y Clientes RTN. Los importes son valores numéricos; los RTN y textos conservan sus caracteres. No ejecuta fórmulas incluidas en nombres o datos de clientes.
- Imprimir reporte completo: abre una ventana independiente y su botón Imprimir reporte permite elegir impresora y papel con el diálogo de Windows. No utiliza el ancho térmico de la factura.

En la aplicación de escritorio, las exportaciones abren una ventana para elegir dónde guardar el archivo. El PDF y el Excel se generan con la misma lógica de consulta y sumas que la pantalla. Son reportes de datos registrados, sin fórmulas externas ni conexiones a Internet.

Los campos históricos que no existían en versiones anteriores se muestran como no disponibles; no se reconstruyen inventando una clasificación fiscal. El resumen avisa del desglose incompleto. Los turnos incluyen todas las operaciones de esos turnos, independientemente del filtro de tipo o pago del libro. Se incluyen turnos que se solapan con el período; su cierre corresponde al turno completo. La auditoría se filtra por fecha a nivel de esta instalación y los clientes son el padrón actual completo.

## Descuento porcentual
Empleados y tercera edad usan los porcentajes configurados por el administrador. Ya no hay descuento en importe fijo para nuevas ventas.

## Pago combinado
Además de efectivo, transferencia o tarjeta, elige Mixto. Introduce lo aplicado a cada medio. La suma debe ser exactamente igual al total; el programa rechaza importes incompletos o excesivos aplicados. Efectivo recibido es el dinero físico entregado; puede ser mayor que el efectivo aplicado y la diferencia es el cambio. Tarjeta y transferencia no generan cambio.

Ejemplo: total L 103.50, efectivo aplicado L 50, tarjeta L 30, transferencia L 23.50 y efectivo recibido L 60: cambio L 10. En reportes se registran L 50 como venta en efectivo; no L 60.

## Caja y turnos
Administrador y sucursal pueden abrir un turno, registrar movimientos físicos con concepto/referencia y cerrarlo indicando el efectivo contado. Solo puede haber un turno abierto por sucursal.

    Efectivo esperado = fondo inicial + ventas emitidas en efectivo + ingresos de caja - egresos de caja
    Diferencia = efectivo contado - efectivo esperado

Tarjeta y transferencia no incrementan el dinero del cajón. Las ventas se vinculan automáticamente al turno abierto de la sucursal. Las nuevas compras requieren caja abierta. Los registros históricos sin turno permanecen como tales.

El cierre conserva esperado, contado y diferencia. No se reabre ni modifica desde el programa. Una factura de un turno cerrado no puede anularse por esta vía: requiere un procedimiento de corrección contable para no cambiar un cierre ya conciliado. Esta versión no implementa notas de crédito o devolución bancaria.

Los ingresos y egresos aquí son movimientos físicos de caja; no calculan por sí mismos crédito fiscal de compras, gastos deducibles o asientos de contabilidad general. Adjunta la referencia del comprobante correspondiente en el movimiento.

## Anulaciones y auditoría
El administrador debe indicar motivo. Se conservan número, importes y detalle originales y se registra responsable y fecha. Anular no reutiliza el número ni devuelve automáticamente un cobro al cliente. Las anulaciones no suman a ventas ni a la caja esperada del turno abierto.

La auditoría comienza en esta versión; no inventa cambios previos. Registra accesos, cuentas de contador, cambio de contraseña (sin contraseña), configuración fiscal/de accesos, productos guardados, emisión/anulación, movimientos/apertura/cierre y exportaciones. El usuario local se identifica como local; no se incorporaron cuentas individuales para cada empleado. La base SQLite no es un archivo de auditoría inalterable frente a quien tenga acceso directo al archivo.

## CAI y facturas
Se mantienen los datos por factura y el consecutivo compartido entre Normal/RTN. Se bloquean emisiones con autorización vencida o rango agotado. Se agregan avisos al quedar 100 o menos facturas o 7 o menos días. Los avisos anticipados no bloquean; el vencimiento/agostamiento sí.

Configura en Facturación y CAI los datos vigentes y el siguiente número realmente disponible, considerando facturas usadas fuera de este programa. No se toman autorizaciones ni correlativos del ZIP del negocio. La nueva aplicación no verifica CAI contra el SAR ni tramita autorizaciones.

Sin CAI configurado se imprime MUESTRA — NO VÁLIDA PARA EFECTOS FISCALES. Revisa emisor, autorización, modalidad de impresión, clasificaciones y cálculos con el responsable contable antes de operar fiscalmente. La fecha de control es la de Windows. Se mantienen original/copia y formatos térmicos de 58/80 mm; la conexión y salida física requieren la prueba con tu impresora real.

## Alcance
Esta es una ampliación de control de ventas, ISV registrado, caja y consulta contable; no es un sistema de contabilidad general con plan de cuentas, asientos, balance general, conciliación bancaria ni presentación automática de declaraciones. No importa la base activa MySQL del negocio.
Se mantienen fotos y edición de precios de la versión anterior, sin cambiar sus datos ni importar productos.

## Pruebas
Se incluyen pruebas de ventas, permisos, fiscalidad local y contabilidad:

    .venv\Scripts\python.exe test_sales.py
    .venv\Scripts\python.exe test_fiscal.py
    .venv\Scripts\python.exe test_accounting.py

También se verificaron desde la interfaz: creación de contador, cambio obligatorio de contraseña, acceso restringido, consulta de RTN e importes, descargas de PDF/Excel y apertura del reporte de impresión. Se comprobó conservación del catálogo al reiniciar/migrar. Se probaron PDF y Excel sin enviar impresiones físicas.

Este ZIP contiene fuentes, recursos, pruebas e instrucciones. No contiene ejecutables, dependencias instaladas, contraseñas de contador ni bases de datos. BUILD_EXE_WINDOWS.bat es opcional si deseas compilar después.


## V22 — INFORMES SAR
En Contabilidad se incluye INFORMES SAR: base gravada al 15 %, base gravada al 18 % y total de venta gravada sin impuesto, después de descuentos. Ejemplo: venta de L 100.00 con ISV del 15 % incluido = base L 86.96; el impuesto L 13.04 no se suma a este informe.
Se aplican los filtros de fecha, sucursal y documentos de Contabilidad. Se excluyen facturas anuladas y consumos especiales sin cobro. Los valores exentos y exonerados no forman parte de la venta gravada. Los documentos históricos sin desglose completo se identifican y se excluyen de las sumas.
Administrador y contador pueden consultar, exportar Excel y descargar PDF para imprimir. El informe es una consulta de los registros del sistema; no presenta declaraciones automáticamente ante el SAR.


## V23 — Eliminar factura con autorización del administrador
En el menú hamburguesa de la sucursal selecciona Eliminar factura, escribe el número de orden y pulsa Buscar orden. Revisa cliente, fecha, importe y estado; indica el motivo y el código de seis dígitos proporcionado por el administrador. La anulación conserva el documento, su consecutivo y la auditoría; no borra filas ni reutiliza números. Se excluye de las ventas emitidas y los informes SAR.
El administrador obtiene el código en Configuración → CÓDIGO PARA ELIMINAR / ANULAR FACTURA → Mostrar código de autorización. Se renueva cada cinco minutos, con barra y tiempo restante. Solo es válido el código del intervalo actual; cinco intentos incorrectos por sucursal bloquean la función hasta el siguiente intervalo. El contador no puede autorizar ni anular. La sucursal solo puede buscar y anular sus propias órdenes.
No se alteran cierres de caja existentes: si la factura pertenece a un turno cerrado se rechaza y requiere corrección contable. El código pertenece a esta instalación y no se sincroniza entre computadoras independientes. Requiere que el programa esté ejecutando V23; inicia con INICIAR.bat.


## V24 — TOTP estándar de 300 segundos
Esta versión sustituye el código propio de V23 por TOTP RFC 6238: SHA1, 6 dígitos, T0=0 e intervalo de 300 segundos. Configura la vinculación antes de usar la anulación desde sucursal; los códigos V23 dejan de ser válidos.
1. Administrador → Configuración → CÓDIGO PARA ELIMINAR / ANULAR FACTURA.
2. Introduce la contraseña actual y pulsa Configurar / renovar clave TOTP.
3. Agrega la clave o enlace otpauth en un autenticador que admita período personalizado. Selecciona TOTP, SHA1, 6 dígitos, 300 segundos. No compartas la clave de vinculación; comparte solo el código de autorización.
4. Escribe el código mostrado por el autenticador y confirma la activación. La vinculación pendiente vence en diez minutos. Renovar la clave mantiene activa la anterior hasta confirmar la nueva.
El administrador también puede mostrar el código en el programa, con barra y cuenta regresiva. Cada código se acepta una sola vez para una anulación; espera el intervalo siguiente para otra. Los intentos incorrectos conservan el límite de cinco por sucursal e intervalo. Solo se acepta el intervalo actual.
La clave se guarda protegida por Windows en este equipo; no se incluye en los informes ni en la auditoría. Funciona sin Internet con el reloj de la PC, que debe coincidir con el del autenticador. No depende de la zona horaria. No hay sincronización entre instalaciones independientes.
Compatibilidad: la documentación de Google Authenticator indica que sus implementaciones pueden ignorar el parámetro period. No se garantiza un intervalo de cinco minutos en esa aplicación; utiliza un autenticador que respete period=300. El programa incluye la visualización del código para el administrador.
Referencias: https://www.rfc-editor.org/rfc/rfc6238.html y https://github.com/google/google-authenticator/wiki/Key-Uri-Format
Verificado con los seis vectores SHA1 del RFC 6238, cambios de intervalo de 300 segundos, activación, clave protegida, rechazo de códigos vencidos/reutilizados, anulación transaccional, renovación y permisos. Se mantienen las pruebas de ventas, pagos mixtos, facturas sin ISV en el detalle e informes SAR.


## V25 — Empleados registrados y beneficiarios de descuentos
Administrador → Configuración → EMPLEADOS Y BENEFICIARIOS DE DESCUENTOS permite crear y editar nombre completo, identidad de 13 dígitos y estado activo. No permite duplicar identidades; se pueden escribir con o sin guiones. Desactivar conserva el historial e impide nuevas ventas con descuento para ese empleado. No se precargan empleados.
Al seleccionar un descuento se abre una ventana de beneficiario. Para EMPLEADOS se selecciona únicamente el nombre de una persona registrada y activa; la sucursal no recibe ni ve su identidad. Para TERCERA EDAD se solicitan nombre completo e identidad. Cancelar o pulsar Escape cancela el descuento. La selección se limpia al completar la venta; los porcentajes continúan siendo los autorizados por el administrador.
El servidor valida el empleado al calcular y nuevamente al guardar. Guarda el beneficiario junto con la venta, en la misma transacción, en un registro privado separado. El administrador consulta HISTORIAL DE BENEFICIARIOS para ver orden, sucursal, fecha, tipo de descuento, nombre e identidad. Cambiar el nombre o identidad actual del empleado no modifica los beneficiarios históricos.
Las identidades de empleados no se envían a sucursal ni se incorporan a la factura, respuestas públicas, libro contable o exportaciones generales. El contador no tiene acceso a la base privada de empleados ni al historial de identidades. Las ventas históricas previas a V25 se conservan sin inventar beneficiarios.
Verificación: altas/edición/inactivación, identidad duplicada, empleado inexistente o inactivo rechazado, permisos, porcentaje protegido, identidad oculta en la factura, beneficiario guardado, identidad requerida para tercera edad e historial inmutable ante edición del empleado. Se mantienen las pruebas de ventas, informes SAR y TOTP.


## V26 — Configuración por secciones y QR del autenticador
Configuración muestra botones superiores: Administrador, Empleados, Historial de descuentos, Autenticador / QR, Categorías, Descuentos y correo, Contadores e Impresora. Solo aparece el contenido de la sección seleccionada. Se conservan los formularios y permisos anteriores.
Para vincular el autenticador: abre Autenticador / QR, escribe tu contraseña actual de administrador y pulsa Configurar / renovar clave TOTP. Aparecerá un QR generado localmente, sin enviar la clave a servicios externos. Escanéalo con una aplicación que respete el intervalo personalizado de 300 segundos, ingresa el primer código y pulsa Confirmar y activar TOTP. También se mantiene la clave y el enlace para vinculación manual.
La vinculación pendiente vence en diez minutos. La clave anterior sigue activa hasta confirmar la nueva. El QR se retira al activar o cerrar la sesión. No se incorpora a archivos ni informes. Generar un nuevo QR no modifica empleados, ventas o datos fiscales.
Inicia con INICIAR.bat. El iniciador comprueba el componente qrcode y lo instala si falta (la instalación requiere Internet). Después, generar y escanear la vinculación funciona sin servicio externo de QR.
Verificación: ocho secciones con un solo panel visible, revisión visual, QR leído por un lector independiente, contenido otpauth exacto con period=300 y activación con el secreto decodificado. Se mantienen las verificaciones de TOTP, empleados, privacidad, descuentos, ventas e informes SAR.


## V27 — Correo de aviso por cada factura anulada
Se mantiene un solo uso por código TOTP de cinco minutos. Al anular una factura se guarda un aviso pendiente en la misma transacción que la anulación y el uso del código. El correo se envía en segundo plano después de confirmar los cambios. Incluye número de orden y factura, sucursal, cliente/RTN, productos, importe original, impuestos, descuento, pago, responsable, fecha y motivo de anulación; adjunta un comprobante HTML de anulación que se puede abrir e imprimir.
En Configuración → Autenticador / QR → AVISOS DE FACTURAS ANULADAS se puede definir el correo de la empresa, consultar estados y solicitar reintentos. Si no se definió un destinatario específico, se utiliza el correo del perfil administrador. Configura servidor, puerto, remitente y credenciales SMTP en Descuentos y correo. Los cambios de destinatario se aplican también a los avisos pendientes.
Sin conexión o con configuración incompleta el aviso queda PENDIENTE y la anulación permanece guardada. El programa intenta enviar inmediatamente tras anular y reintenta pendientes cada cinco minutos mientras esté abierto. No vuelve a enviar un aviso ya marcado ENVIADO ni crea otro aviso al repetir la misma anulación. Una interrupción entre la aceptación SMTP y el registro local puede ocasionar un reenvío; se conserva el mismo Message-ID para identificarlo.
Los avisos corresponden a anulaciones realizadas desde V27; no envía retrospectivamente avisos de facturas previamente anuladas. No se alteran ventas previas ni cierres de caja.
Pruebas: un solo uso del código, aviso persistente e idempotente, contenido y destinatario, falla SMTP con reintento posterior, envío confirmado sin repetición y permisos. SMTP simulado: no se enviaron correos reales durante las pruebas.


## V28 — Modo claro/oscuro y productos SIN DESCUENTO
El botón Modo oscuro / Modo claro está disponible al iniciar sesión y en la cabecera del programa. La elección se guarda en esta instalación y se conserva al reiniciar o cambiar de perfil. El tema modifica las pantallas y ventanas; las facturas mantienen fondo blanco para imprimir.
Administrador → Configuración → SIN DESCUENTO permite elegir una categoría y marcar los productos excluidos. Marcado significa que NO recibe descuento. Cada cambio se guarda inmediatamente y solo el administrador puede modificarlo. No hay productos excluidos por defecto.
El porcentaje de empleados o tercera edad se aplica únicamente al importe de los productos permitidos. Ejemplo: comida L 100 + refresco excluido L 50, descuento 25 % = L 25 de rebaja y L 125 de total. Con 20 % = L 20 de rebaja y L 130 de total. Si todos los productos están excluidos, la rebaja es cero. El cálculo y la validación se realizan en el servidor, se guardan con la venta y conservan las bases e impuestos coherentes para los informes. Las facturas anteriores conservan sus valores.
Verificado: compras mixtas, productos excluidos sin rebaja, todos excluidos, porcentajes de empleado/tercera edad, guardado del detalle, sumas fiscales, rechazo de cambios desde sucursal y conservación del modo de pantalla entre sesiones. Revisado visualmente el inicio y Configuración en modo oscuro.


## V29 — Guardado explícito y reloj blanco
En SIN DESCUENTO, marcar o desmarcar prepara los cambios. Debes pulsar GUARDAR CAMBIOS debajo de los productos para aplicarlos. La pantalla indica cuántos cambios están pendientes y confirma GUARDADO CORRECTAMENTE al guardar y volver a consultar el registro. Puedes marcar en varias categorías y guardarlas juntas. Se conservan las marcas guardadas en versiones anteriores.
El lote se valida y guarda en una sola transacción: si un producto no existe no se aplica parte del lote. Al cerrar el programa con cambios pendientes se solicita confirmación. Cerrar sesión descarta los cambios aún no guardados.
En modo oscuro, la fecha y hora de Honduras se muestran en blanco. Se conserva el formato de 12 horas y su funcionamiento previo.
Verificado: guardado y lectura del lote, rechazo sin cambios parciales, conservación de la validación de descuentos y revisión visual del botón en modo oscuro.


## V30 — Código personal y responsable de caja
Antes de ingresar a una sucursal, abre Administrador → Configuración → Empleados, edita cada empleado y asigna primer nombre, primer apellido y código personal de 4 a 32 letras/números. El código debe ser único; no distingue mayúsculas/minúsculas. El formulario vacío conserva el código anterior. No se muestran códigos existentes después de guardarlos: el administrador puede reemplazarlos. Los empleados sin código siguen disponibles para descuentos, pero no pueden ingresar a caja.
En el acceso a sucursal selecciona el local e ingresa el código personal del empleado. La contraseña compartida de la sucursal ya no permite ingresar a caja; el acceso de administrador y contador mantiene su correo y contraseña. No hay código personal precargado.
Cada sesión muestra el cajero identificado. Apertura, movimientos, cierre, anulaciones y auditoría registran nombre completo e identificador del empleado. Las facturas nuevas muestran el primer nombre y primer apellido configurados por el administrador y conservan una copia histórica de la identificación. No se utiliza un nombre enviado desde el formulario de venta.
Si otro empleado continúa una caja abierta, debe cerrar sesión e ingresar con su propio código. Se conserva quién abrió la caja y se identifica al empleado que cierra y realiza las operaciones siguientes. No se vuelve a sumar el fondo inicial. Las operaciones históricas sin identificación de empleado no se reasignan ni se inventan nombres.
Editar o desactivar un empleado invalida sus sesiones existentes; debe volver a ingresar. La identidad sigue reservada al administrador y el código se verifica mediante hash. La factura conserva el nombre original aunque posteriormente se cambie o desactive al empleado.
Verificado: acceso con código, rechazo de contraseña compartida y códigos duplicados, nombre auténtico en factura, identificación de apertura/cierre/inicio de sesión, invalidación de sesión, historial preservado y campos de acceso ausentes de respuestas públicas. Revisión de la pantalla de caja con un empleado de prueba. Se mantienen las demás verificaciones de ventas, descuentos, TOTP, correo, informes SAR y modos de pantalla.


## V31 — Nombre del sistema y reimpresión desde sucursal
Se sustituye CHICKEN / POS por SISTEMA DE FACTURACIÓN FRY CHICKEN en el inicio y el panel lateral.
En el menú hamburguesa selecciona Reimprimir factura, ingresa el número y espera la consulta automática (Enter consulta de inmediato). Acepta el número fiscal completo, el número de orden o el correlativo fiscal cuando se puede identificar sin ambigüedad. La ventana muestra el total y dos botones: Cancelar e Imprimir. Solo consulta documentos de la propia sucursal.
Imprimir recupera la factura original como COPIA y utiliza la impresora configurada; en navegador abre el diálogo de impresión. No crea una venta, no recalcula precios o impuestos y no consume correlativos. La auditoría registra la solicitud y el empleado responsable. Los documentos anulados se identifican como FACTURA ANULADA.
Verificado: búsqueda por orden y número fiscal, importe, restricciones de sucursal, auditoría, identificación de copia/anulada y conservación de cantidad de facturas y siguiente correlativo. No se envió una impresión física durante las pruebas.


## V32
SIN DESCUENTO utiliza botones de categorías y consulta los productos al abrir su sección. Conserva selección entre categorías y guardado explícito. En administrador se ocultan el logo central y la tuerca superior; Configuración sigue disponible en el menú lateral. Se ajusta la alineación del reloj.


## V33 — Separación de controles
Se ajustan espacios entre campos, etiquetas, formularios y botones en empleados, correo, autenticador, productos, sucursales y diálogos. El cambio de tema es un icono compacto con descripción accesible; el menú hamburguesa ocupa el extremo final después del icono. Se conservan funciones y datos anteriores.


## V34 — Alineación y centrado
Logo y nombre centrados en el panel lateral, botones laterales centrados, botones de Configuración con alto uniforme y distribución centrada. Se alinean el selector de sucursal, tema y menú; el reloj de administrador se desplaza hacia la izquierda. Ajustes adaptables a pantallas más pequeñas.


## V35 — Marca en cabecera del administrador
El logo del administrador se mueve de la barra lateral a la cabecera, reemplazando el título de página. Se muestra SISTEMA DE FACTURACIÓN y FRY CHICKEN en dos renglones. El menú lateral conserva los accesos y dispone de más espacio vertical. Los perfiles de sucursal conservan su cabecera.


## V36 — Respaldo JSON completo automático
Cada guardado de datos actualiza FRYChickenPOS-RESPALDO-COMPLETO.json en %LOCALAPPDATA%\FRYChickenPOS\data. Incluye todas las tablas: empleados y códigos protegidos, contadores y accesos, sucursales, productos, precios, RTN/clientes, facturas, caja, descuentos, exclusiones, CAI, configuración, auditoría y avisos pendientes. Incluye imágenes guardadas en subcarpetas de datos. Los recursos del catálogo incluidos con el programa siguen formando parte del ZIP.
Las actualizaciones utilizan la misma base persistente existente, que tiene prioridad sobre el respaldo. Si falta la base de datos y el JSON está presente en esa carpeta, V36 la recupera antes de iniciar. No importa automáticamente un JSON sobre una base existente ni fusiona datos. El guardado del JSON es atómico para conservar el respaldo anterior si falla su escritura.
Para trasladarlo, conserva una copia privada del JSON. En una instalación sin base existente, coloca el JSON en la carpeta de datos antes de abrir el programa. Contiene información sensible: identidades, ventas y configuración de acceso. Las claves de correo y TOTP protegidas por Windows pueden requerir nueva vinculación al cambiar de computadora.
Probado con empleados, perfiles de contador y ventas: JSON generado automáticamente, restauración completa en otra carpeta de prueba y conteo de facturas verificado. No se modificaron datos de producción durante las pruebas. Las versiones siguientes deben conservar este mecanismo y la ubicación persistente.


## V38 — Exportar e importar catálogo JSON
En Productos y precios, el administrador puede usar Exportar catálogo JSON para descargar un archivo completo de productos. Incluye nombres, categorías, orden de categorías, precio en lempiras y centavos, clasificación de ISV, marcas SIN DESCUENTO e imágenes normalizadas en formato JPEG dentro del propio archivo.
Importar catálogo JSON valida el formato, los precios, impuestos e imágenes antes de guardar. Tras la confirmación, sustituye el catálogo actual completo por el del archivo y conserva las facturas ya emitidas, cuyo detalle histórico está guardado dentro de cada comprobante. El archivo está limitado a 1,000 productos y 80 MB. Solo el administrador puede exportar o importar.

## V39 — Comandas de cocina, almuerzos y metas
Consulta LEEME-V39.txt para configurar las dos impresoras, registrar notas y almuerzos gratis y asignar metas por sucursal. Se conserva el respaldo JSON completo automático de V36 y el catálogo JSON de V38.

## V40 — Respaldo remoto confirmado y emergencia con autenticador
Consulta LEEME-V40-RESPALDOS.txt. Incluye receptor independiente, confirmación antes de finalizar cada factura, bloqueo de nuevas ventas sin conexión, autorización TOTP por 30 minutos, arranque con Windows y recuperación completa en una PC nueva. Se conservan los módulos V39 y la copia JSON local.


## V42 — Menú gratuito autorizado
El administrador asigna platos y refrescos gratuitos. Cada almuerzo exige un plato y un refresco, una unidad de cada uno, sin complementos. Consulta LEEME-V42.txt.


## V43 — Modalidades, envío separado y tarjeta en SAR
Consulta LEEME-V43.txt.


## V44 — Servidor central, terminales y cola durable
Una base y correlativo por sucursal; sesiones/turnos por terminal, empleados autorizados y toda la impresión de facturas/comandas en máquina 1.
