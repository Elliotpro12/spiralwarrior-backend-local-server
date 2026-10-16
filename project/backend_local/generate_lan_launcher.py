#!/usr/bin/env python3
"""Generate the ignored Windows launcher for the LAN backend."""

from pathlib import Path


OUTPUT = Path(__file__).with_name("start_local_server_lan.bat")
CONTENTS = """@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if not errorlevel 1 (
  python run_local_server.py --lan
  goto :finished
)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 run_local_server.py --lan
  goto :finished
)
echo No se encontro Python 3 en PATH.
pause
exit /b 1
:finished
if errorlevel 1 (
  echo.
  echo El backend LAN no pudo iniciar. Revisa el mensaje anterior y que Python 3 este instalado.
  pause
)
endlocal
"""


def main() -> int:
    OUTPUT.write_bytes(CONTENTS.replace("\n", "\r\n").encode("ascii"))
    print(f"Lanzador generado: {OUTPUT}")
    print("El archivo .bat esta excluido de Git; comparte este generador y las instrucciones.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
