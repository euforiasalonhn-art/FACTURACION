# Catálogo de WooCommerce — v.92

El botón GUARDAR aparece al final de la selección de categorías. Confirma el guardado e inicia la descarga en segundo plano cuando la sincronización está activada y hay categorías seleccionadas. Una barra y contadores muestran el avance, los productos revisados y las imágenes descargadas. Al finalizar indica DESCARGA COMPLETA o el motivo del error. La pantalla puede cerrarse mientras PC 1 continúa descargando. Si se cierra completamente el programa, se conserva el catálogo anterior y se podrá reintentar al abrirlo.

Abre Configuración → WOOCOMMERCE con el acceso de Ajustes.

1. Ingresa la URL HTTPS de la tienda y las claves Consumer key y Consumer secret creadas en WooCommerce → Ajustes → Avanzado → REST API. Basta acceso de lectura, asociado a un usuario con acceso al catálogo y a la moneda de la tienda.
2. Guarda la conexión. Consulta las categorías, marca las que se mostrarán y vuelve a guardar. Solo esas categorías alimentan el catálogo local.
3. Configura la correspondencia de impuestos. La clase estándar tiene 15 % inicialmente. Una clase adicional puede asignarse a 18 %, EXENTO o EXONERADO. El JSON usa el slug de la clase WooCommerce. Ejemplo {"":"15","tasa-18":"18"}. Los productos sin impuesto en WooCommerce se importan como EXENTO.
4. Activa la sincronización y presiona SINCRONIZAR AHORA. La revisión automática ocurre cada 5 minutos mientras PC 1 está abierta. Las pantallas de venta consultan el catálogo local actualizado cada minuto.

La moneda debe ser HNL. El precio vigente se importa tal como lo entrega WooCommerce, incluido el precio de oferta activo. Configura en Facturación y CAI si ese precio incluye ISV. El sistema no convierte moneda ni deduce tasas a partir del nombre de una clase.

Se importan productos simples y variaciones publicadas de las categorías seleccionadas. Las variaciones usan la imagen propia o la del padre. Se omiten productos agotados, sin precio y tipos agrupados/externos. Si tienen varias categorías seleccionadas, se usa la primera de la selección. El orden visual puede ajustarse en Categorías.

Cada descarga se valida por completo antes de actualizar precios, fotos y disponibilidad en una transacción. Ante errores de conexión o imágenes, se conserva el último catálogo completo. Las fotos quedan guardadas en la base local. Las imágenes requieren HTTPS sin redirecciones. Claves API guardadas con protección de Windows, con campos vacíos para conservarlas. Al cambiar de computadora se deben guardar nuevamente.

Los productos anteriores quedan fuera del catálogo visible. Sus registros se mantienen para referencias e historial. Los nombres, precios e imágenes nuevos se administran en WooCommerce. Los identificadores locales se conservan por tienda y producto remoto, manteniendo descuentos y permisos asociados al producto.

Preparado según REST API v3 https://woocommerce.github.io/woocommerce-rest-api-docs/ . La prueba de integración utiliza una tienda simulada. Falta conectar y verificar la tienda real con sus claves API.
