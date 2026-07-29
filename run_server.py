#!/usr/bin/env python3
"""Script lanzador del servidor con interfaz CMD para tracear errores.

Uso:
    python run_server.py                 # puerto 8080
    python run_server.py --port 9000     # puerto custom
    python run_server.py --host 0.0.0.0  # acceso externo
    python run_server.py --reload        # auto-reload en desarrollo
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

# Use trading-client app (has all routers: brokers, broker_accounts, intelligence)
_TRADING_CLIENT_DIR = str(Path(__file__).resolve().parent / "trading-client")
if _TRADING_CLIENT_DIR not in sys.path:
    sys.path.insert(0, _TRADING_CLIENT_DIR)

# Change CWD to trading-client so .env and relative DB paths resolve correctly
os.chdir(_TRADING_CLIENT_DIR)

# Banner ASCII
BANNER = r"""
  _               _      _____                     _
 | |             | |    / ____|                   | |
 | |     ___  ___| |_  | (___   ___  __ _ _ __ ___| |__
 | |    / _ \/ __| __|  \___ \ / _ \/ _` | '__/ __| '_ \
 | |___|  __/ (__| |_   ____) |  __/ (_| | | | (__| | | |
 |______\___|\___|\__| |_____/ \___|\__,_|_|  \___|_| |_|

  Sistema de Trading Algoritmico - Servidor Dashboard
"""

# Colores ANSI (CMD moderno / Windows Terminal soporta ANSI)
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
GRAY = "\033[90m"
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
BG_BLUE = "\033[44m"


def enable_ansi_colors() -> None:
    """Habilita colores ANSI en Windows CMD."""
    if sys.platform == "win32":
        os.system("")  # Activa VT100 en Windows 10+


def print_banner() -> None:
    """Imprime el banner de inicio."""
    print(f"{CYAN}{BANNER}{RESET}")
    print(f"  {GRAY}{'=' * 55}{RESET}")
    print(f"  {BOLD}Fecha:{RESET} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  {GRAY}{'=' * 55}{RESET}")
    print()


def print_box(text: str, color: str = BLUE) -> None:
    """Imprime texto dentro de un recuadro coloreado."""
    lines = text.split("\n")
    width = max(len(line) for line in lines) + 4
    top = f"  {color}+{'-' * width}+{RESET}"
    bottom = f"  {color}+{'-' * width}+{RESET}"
    print(top)
    for line in lines:
        padding = width - len(line) - 2
        print(f"  {color}|{RESET} {line}{' ' * padding} {color}|{RESET}")
    print(bottom)


def print_status(label: str, value: str, color: str = GREEN) -> None:
    """Imprime una linea de estado con etiqueta coloreada."""
    print(f"  {color}[{label}]{RESET} {value}")


def print_error(msg: str, exc: Exception | None = None) -> None:
    """Imprime un error con formato CMD."""
    print()
    print(f"  {BG_RED}{BOLD} ERROR {RESET} {RED}{msg}{RESET}")
    if exc:
        print(f"  {GRAY}Tipo:{RESET} {type(exc).__name__}")
        print(f"  {GRAY}Mensaje:{RESET} {exc}")
        print()
        print(f"  {YELLOW}Traceback:{RESET}")
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        for line in "".join(tb).split("\n"):
            if line.strip():
                print(f"  {GRAY}|{RESET} {line}")
    print()


def print_warning(msg: str) -> None:
    """Imprime un warning con formato CMD."""
    print(f"  {YELLOW}[WARN]{RESET} {msg}")


def print_info(msg: str) -> None:
    """Imprime info con formato CMD."""
    print(f"  {BLUE}[INFO]{RESET} {msg}")


def print_ok(msg: str) -> None:
    """Imprime un OK con formato CMD."""
    print(f"  {GREEN}[OK]{RESET} {msg}")


def check_dependencies() -> bool:
    """Verifica que las dependencias criticas esten instaladas."""
    missing: list[str] = []
    for pkg in ["fastapi", "uvicorn", "sqlalchemy", "pydantic"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print_error(f"Faltan dependencias: {', '.join(missing)}")
        print(f"  {GRAY}Instala con:{RESET} pip install {' '.join(missing)}")
        return False
    return True


def check_env() -> None:
    """Verifica configuracion del entorno."""
    env_path = Path(".env")
    if not env_path.exists():
        print_warning("No se encontro .env - usando valores por defecto")
        print(f"  {GRAY}Copia .env.example a .env para configurar{RESET}")
    else:
        print_ok("Archivo .env detectado")


def check_database() -> bool:
    """Verifica que la base de datos este accesible."""
    try:
        from app.database.session import SessionLocal

        session = SessionLocal()
        session.execute(__import__("sqlalchemy").text("SELECT 1"))
        session.close()
        print_ok("Base de datos conectada")
        return True
    except Exception as exc:
        print_error("No se pudo conectar a la base de datos", exc)
        print(f"  {GRAY}Ejecuta: alembic upgrade head{RESET}")
        return False


def print_routes_info(host: str, port: int) -> None:
    """Imprime informacion de rutas disponibles."""
    info = (
        f"  Dashboard:  http://{host}:{port}\n"
        f"  Swagger:    http://{host}:{port}/docs\n"
        f"  Health:     http://{host}:{port}/health\n"
        f"  API:        http://{host}:{port}/api/..."
    )
    print_box(info, CYAN)
    print()


def run_server(host: str, port: int, reload: bool) -> int:
    """Inicia el servidor con manejo de errores y logging estilo CMD."""
    enable_ansi_colors()
    print_banner()

    # Pre-flight checks
    print(f"  {BOLD}Pre-flight checks:{RESET}")
    print(f"  {GRAY}{'-' * 40}{RESET}")

    if not check_dependencies():
        return 1

    check_env()

    if not check_database():
        return 1

    print()
    print(f"  {BOLD}Configuracion del servidor:{RESET}")
    print(f"  {GRAY}{'-' * 40}{RESET}")
    print_status("Host", host, BLUE)
    print_status("Port", str(port), BLUE)
    print_status("Reload", "ON" if reload else "OFF", YELLOW if reload else GRAY)
    print_status("Python", sys.version.split()[0], GRAY)
    print_status("PID", str(os.getpid()), GRAY)
    print()

    print_routes_info(host, port)

    # Arrancar servidor
    try:
        import uvicorn

        print(f"  {GREEN}[STARTING]{RESET} Iniciando uvicorn...")
        print(f"  {GRAY}Presiona Ctrl+C para detener{RESET}")
        print(f"  {GRAY}{'=' * 55}{RESET}")
        print()

        uvicorn.run(
            "app.api.app:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info",
            access_log=True,
            app_dir=os.path.join(os.path.dirname(__file__), "trading-client"),
        )
        return 0

    except KeyboardInterrupt:
        print()
        print(f"  {YELLOW}[STOPPED]{RESET} Servidor detenido por el usuario")
        print(f"  {GRAY}Hasta pronto!{RESET}")
        print()
        return 0

    except OSError as exc:
        if "10013" in str(exc) or "Errno 13" in str(exc):
            print_error(f"Puerto {port} en uso o sin permisos", exc)
            print(f"  {GRAY}Prueba con otro puerto: python run_server.py --port 9090{RESET}")
        else:
            print_error("Error de red al iniciar el servidor", exc)
        return 1

    except Exception as exc:
        print_error("Error fatal al iniciar el servidor", exc)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lanzador del servidor Trading System con interfaz CMD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python run_server.py                    Puerto 8080, localhost
  python run_server.py --port 9000        Puerto 9000
  python run_server.py --host 0.0.0.0     Acceso desde otras maquinas
  python run_server.py --reload           Auto-reload (desarrollo)
        """,
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host de escucha (def: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Puerto de escucha (def: 8080)")
    parser.add_argument("--reload", action="store_true", help="Auto-reload en desarrollo")
    args = parser.parse_args()

    return run_server(args.host, args.port, args.reload)


if __name__ == "__main__":
    sys.exit(main())
