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
