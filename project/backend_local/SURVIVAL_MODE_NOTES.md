# Survival Mode (MPO) on the local backend: status notes

Estado al momento de esta nota. Lo que sigue está etiquetado como **Observado**
(visto en el juego o en el código del cliente), **Inferido** (consistente con la
evidencia, no confirmado) o **Desconocido**.

## Resumen

- Survival entra y llega a la pantalla de carga de partida en la cuenta de prueba.
- La partida **no termina**: el cliente falla al montar la plantilla de partes del
  rival y nunca llega a una ronda.
- Ninguna batalla Survival se registra todavía, así que la fila de temporada
  "Complete 1 Survival Mode battles" (1112551986) no puede completarse.

## Flujo de entrada (Observado)

1. Nivel 5 desbloquea Survival (`LevelOpen`, fila 5, `Goto = ChijiKaiju`).
   En la cuenta de prueba se fijó nivel 5 editando `profile.json` a mano, porque el
   servidor no sube de nivel con experiencia (Desconocido: la curva de experiencia).
2. Paso de guía 1047 → 1052 (`GuideData`): tocar el texto "Survival Mode" de la
   tarjeta de Challenge abre la pantalla de arenas.
3. Novice Arena cuesta 200 de oro; la cuenta tiene 3 entradas gratis al día.
4. Al entrar, el cliente envía `ECS_BoutOpr` con `boutOpr` 10 y `raceType` 3
   (`E_RaceType.MPO_RACE`).

## Mensajes de partida (Observado, cliente → servidor)

| Operación | Nombre | Respuesta del servidor (estado actual) |
|---|---|---|
| 10 | E_RACE_ROBOT_GAME | Eco 10 y `ESC_Race` con `RaceProto` (2 jugadores). |
| 20 | E_MPO_WAITING_OTHER_OVER | Servidor envía 20 con `param1` = 81 jugadores (escena ChiJi). |
| 23 | E_MPO_NOTIFY_REPORT_EQUIPMENT | Servidor envía 23: abre la rejilla de módulos. |
| 24 | E_MPO_REPORT_EQUIPMENT | Cliente envía 9 IDs de equipo. Servidor responde 12. |
| 4 | E_RACE_TICK | Eco 4 (no-op en el cliente). |
| 12 | E_BOUT_BEGIN | Eco 12. |

Antes, responder `E_RACE_ERROR` (0) mostraba "You were disconnected from the game"
o devolvía al inicio. Por eso las operaciones no reconocidas se responden con eco
en el caso Survival (`response_bout_opr_for_request`).

## Tutorial de módulos (Observado)

- `beginChijiGuide` corre si `RaceHistory(MPO).Total == 0` y `winRound == 0`
  (`project.js` ~95877). Es un tutorial guionizado y se repite mientras esa
  condición se cumpla.
- Pasos: diálogos, arrastrar el módulo de la casilla 1 a la 6, tocar el badge de
  Link, y luego la selección de Top y Battle.
- `onBtnPlay` muestra el panel "Waiting for opponents..." (`WaitPlayerLoadingPanel`).
  Se quita en `BattleControl.initPlay`, que depende de que `onBoutBegin` complete.

## Estructura de RaceProto (Observado en el código generado; Inferido en valores)

- `RaceProto`: 1 RaceID, 2 RaceType, 3 BoutList (`ContainerIntBoutProto` idx, val),
  5 WinChair, 6 RaceEndTime, 7 RaceStep, 10 RacePlayers, 14 Equipments, 15 ToyTopList
  (en `RacePlayerProto`), 16 PartKern, 17 Talents.
- `BoutProto`: 1 BoutBeginTime, 2 BoutEndTime, 3 RandomSeed, 4 WinChair,
  5 BoutPlayers (`ContainerIntBoutPlayerProto` idx=chair, val).
- `BoutPlayerProto`: 1 ToyTopIdx, 2 PointX, 3 PointY.
- `RacePlayerProto` (ToyTopList entries): idx = ID de parte, val = `ToytopPartProto`
  {1 Level, 2 Piece, 3 PartAs (1 Top, 2 Mid, 3 Bot), 4 Skin, 5 CurSkin, 6 LocationKerns}.
- Inferido: los valores de PointX/PointY (0,0 y 1,0) y los tiempos son marcadores;
  el rango real no está verificado.

## Bloqueo actual (Observado)

- Tras añadir `BoutList` (evita el fallo de `getBoutBeginPos`) y `ToyTopList`
  (evita `ChooseUI9V9.dealUpDownShow`), el cliente lanza:
  `TypeError: Cannot read property 'data' of undefined` en
  `dealPartKernAndTalent` (`project.js` ~12520). Se llama al montar `matchToyTopInfoArray`.
- Hipótesis (Inferido, sin confirmar): `partDataCache.getPartLevel` devuelve
  `null` para alguna de las tres piezas de la plantilla (2001 Top, 2002 Mid, 2003 Bot).
  Revisar `setLevelPart` (`project.js` ~201061) y `TopPartData` (la fila 2001 tiene
  `location: 0`; comprobar que `PartAs` corresponde a `location + 1`).

## Pendiente

1. Resolver el `data` de `dealPartKernAndTalent` y llegar a la primera ronda.
2. Ronda: `E_BOUT_BEGIN` real, `E_BOUT_END` (13), eliminación (25) y `E_RACE_END` (14).
   Desconocido: si la batalla la simula el cliente con `RandomSeed` y el servidor
   solo valida el resultado.
3. Contar RaceMark 1 (MPO) al terminar una batalla. Hoy `RaceMark` 1 no tiene
   ningún contador en `progression_counters`.
4. Verificar en el juego la fila de temporada y su reclamo de 150 Pass EXP.

## Cómo reproducir (cuenta de prueba local)

- Servidor: `python run_local_server.py` con `SPIRAL_ADMIN_TOKEN` y `SPIRAL_ADB`.
- Cuenta `swtest15` (datos locales, no commitear perfiles). Nivel 5 se fija editando
  `data/accounts/2/profile.json`; la copia previa del perfil no está en el repo.
- Logs de la partida: `logs/` (ignorados por Git) y `logcat` del emulador para los
  errores de JavaScript (`jswrapper: JS: [ERROR]`).

## Estado tras la sesión de búsqueda (2026-11-16)

Observado:
- Survival entra con 200 de oro (la opción Free pide un anuncio, no soportado).
- Tras el emparejamiento el juego muestra "All players found" y luego Exploring (rejilla de módulos).
  El botón de flecha inferior derecha inicia la búsqueda ("Searching").
- Reenviar la operación 23 en los ticks siguientes hace que la búsqueda termine una vez, pero el juego
  vuelve a buscar y no envía la operación 24.
- Llamar a `ChijiSearch.overSearch()` desde el juego (vía Frida, sin tocar el servidor) produce:
  `TypeError: Cannot read property 'data' of undefined` en `dealPartKernAndTalent` (project.js ~12520),
  llamado desde `MatchMgr.init` (~12507), con `players` = `getMatchPlayerArray()` de `_Race.RacePlayers`.

Inferido (sin confirmar):
- El cliente recorre `RacePlayerProto.ToyTopList` como diccionario (`z` en project.js ~185056) y usa la
  clave como ID de pieza, pero la decodificación da un arreglo de contenedores `{idx, val}`. La forma que
  espera el cliente no coincide con la que enviamos (ID de pieza como `idx`).
- Hace falta leer `_Race.RacePlayers` tal como lo recibe el cliente para confirmarlo. Leer módulos internos
  con `require` provoca SIGSEGV en el juego; no hacerlo.

Pendiente: alinear `ToyTopList` con lo que el cliente espera, luego llegar a la ronda (12/13), eliminación
(25) y fin (14), y contar RaceMark 1.

## Resultado: batalla Survival completa (2026-11-16)

Observado en el juego (cuenta de prueba):
- Entrada a Novice Arena (200 de oro), búsqueda, Exploring, combate con rondas (12/13) y fin de partida (14).
- Pantalla de resultado "One more try" con victoria y ranking 0/81.
- Fila de Trade Introduction "Complete 1 Survival Mode battles" pasa a 1/1 y el grupo se reclama:
  GP 20 → 25, nivel 5 → 6, intercambio 1280716853 con `success: true`.

Lo que hizo funcionar la batalla (cambios en ws_probe_server.py):
- Rival con tres tops completos: PartAs 1/2/3 con piezas de Behemoth (2001-2003), Athena (2004-2006)
  y Kaguyahime (2028-2030). El selector de tops recorre tres posiciones en orden aleatorio.
- MainTop del rival = 1 (índice del top líder, base 1; el cliente resta 1).
- Operación 13 (fin de ronda) y 4 (tick) respondidas con eco; 14 (fin de partida) respondida con
  SC_BoutOpr {boutOpr 14, WinChair} usando el ganador que envía el cliente (param2).
- Tras contar la batalla se envía la sincronización de tareas, para que la fila se actualice.

Contadores:
- RaceOver de MPO (RaceMarks 1) = clave `condition:0:0:3:race:1`. Las filas de Trade Introduction
  (1278227764) y de temporada (1112551986, máximo 20) comparten esa clave.

Pendiente:
- Fila de temporada: 1 de 20 batallas.
- Recompensas de la batalla (RaceReward) y mail de premios: no verificados.
- Derrotas y eliminación (25) no probadas: la partida probada terminó con victoria.
