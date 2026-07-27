> **OBSOLETO** — Este documento describe la instalación del monolito legacy (`app/` en la raíz) y no aplica al cliente activo (`trading-client/`).  
> Para la arquitectura actual, consultar [`CURRENT_ARCHITECTURE_AUDIT.md`](./CURRENT_ARCHITECTURE_AUDIT.md).  
> **No actualizar este archivo.**

# Instalación local

## Requisitos

- Python 3.12 o superior
- Docker y Docker Compose (opcional pero recomendado)
- Git

## Pasos

### 1. Clonar o copiar el proyecto

```powershell
cd C:\Users\nokturno\Desktop\TRADING PROJECT
```

### 2. Crear entorno virtual

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Instalar dependencias

```powershell
pip install -e ".[dev]"
```

### 4. Configurar variables de entorno

```powershell
copy .env.example .env
```

Edita `.env` y ajusta los valores. Para usar SQLite en desarrollo:

```env
DATABASE_URL=sqlite:///./trading.db
TRADING_MODE=backtest
LIVE_TRADING_ENABLED=false
```

Para usar PostgreSQL con Docker, deja la URL por defecto de `.env.example`.

### 5. Ejecutar migraciones

```powershell
alembic upgrade head
```

### 6. Verificar estado

```powershell
python -m app.cli health
python -m app.cli config
```

### 7. Ejecutar pruebas

```powershell
pytest -v
```

## Solución de problemas

- Si `alembic` no se reconoce, activa el entorno virtual.
- Si PostgreSQL no responde, verifica que el contenedor esté levantado:
  `docker compose up db`.
- Para regenerar la base de datos desde cero:
  `alembic downgrade base && alembic upgrade head`.
