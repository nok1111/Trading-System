@echo off
title Trading System Server
color 0A
echo.
echo  ============================================
echo   Trading System - Lanzador del Servidor
echo  ============================================
echo.
echo  Selecciona una opcion:
echo.
echo   [1] Iniciar servidor (puerto 8080)
echo   [2] Iniciar servidor (puerto personalizado)
echo   [3] Iniciar servidor con auto-reload (dev)
echo   [4] Iniciar servidor (acceso externo 0.0.0.0)
echo   [5] Salir
echo.
set /p opcion="Opcion [1-5]: "

if "%opcion%"=="1" (
    .venv\Scripts\python.exe run_server.py --port 8080
)
if "%opcion%"=="2" (
    set /p puerto="Puerto: "
    .venv\Scripts\python.exe run_server.py --port %puerto%
)
if "%opcion%"=="3" (
    .venv\Scripts\python.exe run_server.py --reload --port 8080
)
if "%opcion%"=="4" (
    .venv\Scripts\python.exe run_server.py --host 0.0.0.0 --port 8080
)
if "%opcion%"=="5" exit /b 0

echo.
pause
