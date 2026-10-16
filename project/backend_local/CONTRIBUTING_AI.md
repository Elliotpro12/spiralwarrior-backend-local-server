# Guía para agentes de vibe coding

## Estado y alcance

Este código implementa un backend local de compatibilidad para Spiral Warrior.
No es una copia del backend original. La estimación vigente es **como mucho
25% del backend original reconstruido**. No aumentes esa cifra contando rutas
sintéticas, operaciones solo probadas en aislamiento o código que no se ha
verificado en el cliente.

Antes de trabajar, lee:

1. `README.md` en la raíz del repositorio.
2. `project/backend_local/README_GITHUB.md`.
3. Los informes enlazados por la tarea y el flujo que vas a tocar.

En cada hallazgo, separa claramente:

- **Observado:** captura o comportamiento visto en el cliente.
- **Inferido:** explicación compatible con la evidencia, aún no confirmada.
- **Desconocido:** contrato, regla o respuesta que todavía no se conoce.

No inventes rutas, campos de protocolo, recompensas, topes, tasas, errores ni
respuestas del servidor original. Las respuestas locales sintéticas deben
identificarse como tales.

## Herramientas del proyecto

### Para ejecutar o editar el backend

- Windows 10/11, PowerShell y Git.
- Python 3.10 o posterior. El servidor usa la biblioteca estándar; los catálogos
  locales del juego se proporcionan aparte y no forman parte del repositorio.
- Node.js/npm solo para tareas de JavaScript del cliente o para instalar REA;
  no es requisito para arrancar el backend Python.

### Para reproducir el cliente en Android

- Para las pruebas dinámicas del cliente: LDPlayer o MuMu Player con acceso
  root y ADB local activado, o un teléfono con root. Sin uno de esos entornos,
  puedes trabajar en el backend y hacer análisis estático, pero no reproducir
  esas pruebas dinámicas.
- Android SDK Platform-Tools (`adb`) instalado en la PC y conexión ADB local
  activa para instalar el cliente, interactuar con el dispositivo y recopilar
  logs.
- Frida en la PC y `frida-server` compatible con la arquitectura y versión de
  Frida de la instancia Android. En la investigación quedó registrada Frida
  17.16.0; cada colaborador debe verificar sus propias versiones.
- Android SDK Build-Tools (`aapt`, `apksigner`, `zipalign`) y Apktool para
  inspeccionar o validar paquetes locales. Las notas del proyecto registran
  Build-Tools 35.0.1 y Apktool 3.0.3.

### Para análisis inverso

- REA (`morluto/rea`) con su skill `reverse-engineer-anything` y, cuando se
  necesite integración con el agente, su configuración MCP.
- Ghidra 12.1.4 o IDA Free para análisis nativo; son alternativas, no hace falta
  instalar ambos.
- Androguard 4.1.4 para inspección programática de DEX.
- JADX puede ayudar con Java/DEX, pero la última revisión del entorno no lo
  encontró en `PATH`; confirma su instalación antes de contar con él.
- Frida para observaciones dinámicas. Los hooks son instrumentos de diagnóstico:
  cuando una corrección deba quedar permanente, implementa el cambio en el
  cliente/backend y repite la prueba sin hooks.

Las versiones anteriores describen la estación de investigación, no una lista
de dependencias que el proyecto instale por su cuenta. No subas instaladores,
emuladores, APKs, `frida-server`, bases de Ghidra/IDA ni claves.

## Instalar REA

La instalación recomendada es pedirle al agente que prepare REA y revise su
propio plan de configuración. Puedes darle esta instrucción:

> Instala la skill REA `reverse-engineer-anything` desde
> https://github.com/morluto/rea y configúrala para este agente si hace falta.
> Primero revisa los requisitos y el plan de cambios. Reutiliza Ghidra o IDA si
> ya están instalados; no instales otro motor de análisis ni cambies ajustes
> existentes sin explicarme qué modificarás. Al terminar, confirma qué skill y
> herramientas quedaron disponibles.

La instalación solo de la skill se documenta como:

```powershell
npx skills add morluto/rea --skill reverse-engineer-anything
```

Para la configuración guiada de REA/MCP, la documentación del proyecto REA usa
`npx rea-agents setup`. REA requiere una versión compatible de Node.js: 22.x
(22.19 o posterior), 24.x (24.11 o posterior) o 26 o posterior. Instalar la
skill no instala por sí solo el servidor MCP ni un motor nativo. El agente debe
verificar su disponibilidad y pedir aprobación antes de cambios de
configuración que la requieran.

Fuentes: <https://github.com/morluto/rea> y
<https://github.com/morluto/rea/blob/main/docs/installation.md>.

## Flujo de trabajo esperado

1. Reproduce el problema con una cuenta y perfil temporales. No modifiques ni
   uses la cuenta beta personal del dueño del proyecto.
2. Identifica el mensaje y callback de cliente con una traza acotada. Guarda
   evidencia sin credenciales, tokens, correos ni datos personales.
3. Implementa el contrato mínimo respaldado por evidencia y valida entradas,
   propiedad del jugador, persistencia, reintentos e idempotencia.
4. Añade una prueba aislada usando archivos temporales. No cambies perfiles
   reales para ejecutar verificaciones.
5. Si el flujo depende de Cocos, confirma en el emulador qué estado muestra el
   cliente y prueba la corrección sin Frida cuando ya exista un cambio
   permanente.
6. Actualiza el informe del sistema con lo probado, lo que no se probó y las
   hipótesis que siguen abiertas.

No agregues un handler de éxito genérico para silenciar errores. El backend
debe devolver el estado sincronizado que espera el cliente y no acreditar dos
veces un reintento.

## Datos y privacidad

- No subas bases SQLite, perfiles, cuentas, correos de prueba, logs, tokens,
  respuestas JWT, volcados, capturas con información personal ni archivos de
  configuración local.
- Los catálogos de `data/*.json` proceden de tablas del cliente. Están
  excluidos de Git hasta revisar permisos. No fuerces su inclusión.
- Mantén el APK original y el APK parcheado fuera del repositorio. El `.gitignore`
  los bloquea por extensión; no uses `git add -f` para saltarte esa protección.
- El listener de LAN es solo para pruebas en una red confiable. No abras puertos
  al Internet ni lo presentes como backend listo para producción.
- El generador `generate_lan_launcher.py` se puede compartir; el `.bat` que crea
  es local y Git lo ignora. No lo fuerces al repositorio.
- No añadas una licencia abierta al repositorio hasta resolver los derechos de
  cada componente y de los datos que se decida incluir.

## Inicio sugerido para una tarea

> Lee la guía del agente y el informe del sistema solicitado. Resume la
> evidencia existente y los desconocidos antes de editar. Trabaja con datos
> temporales, conserva el límite de reconstrucción del 25% o menos y no cambies
> APKs, recursos recuperados, cuentas reales ni ajustes globales de REA.
