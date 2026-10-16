# Backend comunitario de Spiral Warrior

Este repositorio contiene el código del backend local que usamos para probar
una restauración comunitaria de Spiral Warrior. **No es el backend original**
y no se comunica con él.

## Alcance real

La estimación del equipo es que se ha reconstruido **como mucho un 25% del
backend original**. Es un límite prudente, no un porcentaje medido contra una
lista completa de servicios: el servidor original no está disponible y buena
parte de sus rutas y reglas siguen siendo desconocidas.

Lo que existe es un backend de compatibilidad basado en solicitudes observadas,
pruebas del cliente y datos sintéticos o extraídos localmente. Entre los flujos
con implementación parcial o pruebas están las cuentas locales, perfiles
separados, Adventure, algunas recompensas e inventario, piezas y alineaciones,
algunas operaciones GP, campaña PvE, compras locales gratuitas y el protocolo
de gacha. El correo y el ranking son servicios sintéticos de prueba. Consulta
[`project/backend_local/README_GITHUB.md`](project/backend_local/README_GITHUB.md)
para los detalles y las limitaciones.

Siguen pendientes, entre otros, la progresión completa de nivel y GP, varias
recompensas, anuncios recompensados sin anuncios, partes de PvE, el flujo de
gacha desde la interfaz y los servicios sociales. Las tasas y reglas que no se
han observado se marcan como desconocidas; no se presentan como comportamiento
del servidor original.

## Ejecutar en Windows

Se necesita Python 3.10 o posterior. El servidor usa la biblioteca estándar de
Python, más los catálogos de datos locales que no se incluyen en este repositorio
porque proceden del cliente del juego y requieren una revisión de derechos.
Consulta [`project/backend_local/data/README.md`](project/backend_local/data/README.md)
antes de preparar esos archivos.

Para ejecutar en esta PC, usa `python project/backend_local/run_local_server.py`.
Las instrucciones para probar desde un teléfono en la misma red Wi-Fi, generar
un lanzador `.bat` local o configurar el firewall están en
[`project/backend_local/README_GITHUB.md`](project/backend_local/README_GITHUB.md).

El modo LAN no incluye HTTPS ni está preparado para exponerlo a Internet. No
uses cuentas reales ni publiques la dirección IP de tu red.

## Para contribuir con un agente de programación

Lee [`project/backend_local/CONTRIBUTING_AI.md`](project/backend_local/CONTRIBUTING_AI.md)
antes de cambiar el servidor. Ahí están el flujo de trabajo, la lista de
herramientas, la instalación de REA y las instrucciones iniciales para el
agente. REA es la skill de análisis enlazada por el proyecto original:
<https://github.com/morluto/rea>.

## APK, recursos y licencia

Este repositorio no incluye el APK modificado, el APK original ni los recursos
recuperados. No los subas sin confirmar que tienes autorización para
redistribuirlos, y tampoco publica enlaces de descarga a los APKs. El código de
backend y los catálogos derivados del cliente tienen licencias y procedencias
distintas; **no se asigna una licencia al repositorio hasta revisar qué partes
podemos licenciar**. Un repositorio privado tampoco concede derechos que no
tengas.

El `.gitignore` deja visible solo una selección del backend y excluye APKs,
respaldos, recursos extraídos, investigaciones locales, datos de cuentas,
logs, claves de firma y catálogos JSON derivados del juego. Revisa `git status`
antes de cada publicación y no fuerces archivos ignorados sin una revisión de
procedencia y permisos.

