# Backend local de Spiral Warrior

Este código es una implementación comunitaria de compatibilidad para pruebas
locales. **No es el backend original.** La estimación del equipo es que se ha
reconstruido como mucho el **25% del backend original**; no tenemos un inventario
completo que permita calcular una fracción exacta.

## Qué incluye

- Acceso local por usuario o correo, sesiones de prueba y perfiles separados.
- Servidor HTTP para el flujo de acceso, avisos locales, compras de prueba,
  correo y respuestas de ranking sintéticas.
- Servidor WebSocket con sincronización de perfil y handlers parciales para
  Adventure, recompensas, inventario/piezas, algunas operaciones GP, campaña
  PvE y Lottery.
- Persistencia local mediante SQLite para cuentas y JSON por perfil.

Los informes de investigación locales documentan la evidencia de cada flujo.
Un handler o una respuesta sintética no demuestra que el servidor original
tuviera el mismo comportamiento.

## Qué falta

La progresión de nivel y GP está incompleta; algunas rutas de PvE y recompensas
no están implementadas; las recompensas de anuncios siguen en progreso; el
flujo de Lottery necesita una prueba completa desde la interfaz; y Friend/Chat
quedan fuera del contrato confirmado. El ranking y el correo son fixtures de
prueba. No hay tasas, topes ni elegibilidad confirmados para varios sistemas.

## Ejecutar

Requisitos: Windows 10/11 y Python 3.10 o posterior. El backend Python usa la
biblioteca estándar. Para probar el cliente también hacen falta un emulador,
ADB y, para observación dinámica, Frida; consulta
[`CONTRIBUTING_AI.md`](CONTRIBUTING_AI.md).

Para repetir las pruebas dinámicas documentadas, el dispositivo debe ser un
emulador con acceso root y ADB local activado, o un teléfono con root. También
necesitas `adb` instalado y conectado desde la PC. El backend se puede ejecutar
y estudiar por separado sin ese dispositivo.

Para ejecutar en esta PC, desde la raíz del repositorio:

```powershell
python project/backend_local/run_local_server.py
```

Para iniciar directamente en la red local, usa:

```powershell
python project/backend_local/run_local_server.py --lan
```

El modo LAN enlaza los listeners a la interfaz de red, detecta la IPv4 privada
de esta PC y anuncia HTTP en el puerto `18765` y WebSocket en `18766`. El
teléfono y la PC deben estar en la misma red local, y el cliente debe apuntar a
la IP que imprime el servidor. Si la detección automática escoge otra interfaz,
puedes indicar la IPv4 asignada a la PC:

```powershell
python project/backend_local/run_local_server.py --lan --lan-ip 192.168.1.25
```

### Generar un lanzador `.bat` local

El repositorio incluye el generador, pero excluye todos los `.bat`. Para crear
el lanzador LAN junto al generador, desde la raíz ejecuta:

```powershell
python project/backend_local/generate_lan_launcher.py
```

Después puedes iniciarlo así:

```powershell
.\project\backend_local\start_local_server_lan.bat
```

El `.bat` generado queda ignorado por Git; comparte el script generador y estos
comandos, no el archivo generado.

### Firewall de Windows para la subred local

Si Windows bloquea conexiones entrantes, abre PowerShell como administrador y
crea una regla limitada a los dispositivos de la subred local:

```powershell
Get-NetFirewallRule -DisplayName 'Spiral Warrior LAN beta backend' -ErrorAction SilentlyContinue |
  Remove-NetFirewallRule
New-NetFirewallRule -DisplayName 'Spiral Warrior LAN beta backend' `
  -Direction Inbound -Action Allow -Protocol TCP `
  -LocalPort 18765,18766 -RemoteAddress LocalSubnet -Profile Any
```

Para quitarla luego:

```powershell
Get-NetFirewallRule -DisplayName 'Spiral Warrior LAN beta backend' -ErrorAction SilentlyContinue |
  Remove-NetFirewallRule
```

El modo LAN no ofrece HTTPS y no se debe exponer a Internet. Las contraseñas y
sesiones de esta build son para pruebas; no uses cuentas reales.

## Catálogos y archivos locales

Los catálogos del cliente en `data/*.json`, las bases, perfiles, logs y
respuestas experimentales no se distribuyen. Consulta
[`data/README.md`](data/README.md). El fixture
`experiments/area-list-localhost.base64` sí se incluye porque es una respuesta
sintética creada para la prueba local, no una captura del servidor original.

Sin los catálogos locales algunas funciones quedan vacías o incompletas. No se
ha verificado cada sistema con los archivos de datos ausentes.

## Componentes

- `server.py`: rutas HTTP locales.
- `ws_probe_server.py`: protocolo WebSocket local.
- `account_store.py`: cuentas, credenciales con hash y sesiones de prueba.
- `mail_fixture.py`: estado del correo sintético.
- `run_local_server.py`: lanzador local/LAN.

El servidor se limita a los contratos observados o marcados como sintéticos;
rechaza métodos no implementados. No configures una instancia pública con este
código sin completar autenticación, transporte cifrado, seguridad operacional,
validación y revisión de datos.

## Licencia y APK

No se incluye el APK original, el APK modificado ni recursos recuperados. No se
ha asignado una licencia al repositorio porque aún se revisan los derechos del
código y de los datos derivados del cliente. No agregues una licencia abierta
ni subas catálogos o binarios hasta terminar esa revisión.
