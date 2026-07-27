# Revisión de Seguridad

> **Fecha**: 2025-01  
> **Propósito**: Documentar los hallazgos de seguridad del estado actual, con severidad, explotabilidad, corrección propuesta y fase de aplicación.  
> **Alcance**: `trading-client/`, `auth-server/`, configuración, despliegue.

---

## Hallazgos

### H-1. Claves de IA guardadas pero nunca usadas (bug funcional + confusión de modelo)

**Severidad**: Media  
**Explotabilidad**: No explotable directamente, pero indica un modelo de datos confuso.

**Descripción**:  
`services/auth.py::get_current_user()` (`trading-client/app/services/auth.py:41-59`) construye un `LocalUser` sin poblar los campos `ai_*_enc` ni `binance_api_key_enc`:

```python
# trading-client/app/services/auth.py:54-59
return LocalUser(
    id=license_info.get("user_id", 0),
    email=license_info.get("email", ""),
    username=license_info.get("username", ""),
    subscription=license_info.get("subscription", "free"),
)
```

Las ramas `if current_user.ai_groq_key_enc` en `routes/ai_agent.py:77` y `if current_user.ai_gemini_key_enc` en `routes/ai_agent.py:82` son **siempre falsas**. Las claves almacenadas en `user_settings` para IA nunca se recuperan vía `LocalUser`.

Además, existe confusión sobre dónde viven las claves: `UserSettings` (`trading-client/app/database/models/user_settings.py`) tiene campos `binance_api_key_enc`, `ai_groq_key_enc`, etc., pero `LocalUser` también declara esos campos (líneas 29-36) sin poblarlos.

**Corrección propuesta**:  
- Fase 1b: `get_current_user()` debe consultar `user_settings` y poblar los campos `binance_api_key_enc` (solo para broker; las de IA se abordan en Fase 3).
- Fase 3: Poblar también `ai_*_enc` desde `user_settings`.
- Eliminar la rama fallback `current_user.binance_api_key_enc` (línea 27 de `helpers.py`) que ya nunca funcionará.

**Fase de aplicación**: 1b (broker), 3 (IA).

---

### H-2. `ENCRYPTION_KEY` con fallback adivinable

**Severidad**: Alta  
**Explotabilidad**: Alta si se tiene acceso al filesystem local o al `.env`.

**Descripción**:  
`services/crypto.py:12-25` deriva la clave Fernet de `sha256(AUTH_SERVER_URL)` si `ENCRYPTION_KEY` no está configurada:

```python
# trading-client/app/services/crypto.py:16-22
key = settings.ENCRYPTION_KEY
if not key:
    seed = getattr(settings, "AUTH_SERVER_URL", "alvora-local-key")
    derived = hashlib.sha256(seed.encode()).digest()
    key = base64.urlsafe_b64encode(derived)
```

`AUTH_SERVER_URL` es `"http://76.13.180.80:8000"` por defecto (`config.py:28`). Cualquiera que sepa la URL del auth-server (o lea el `.env`) puede derivar la clave Fernet y desencriptar todas las API keys almacenadas en `user_settings`.

**Corrección propuesta**:  
- Fase 2: Eliminar el fallback. `ENCRYPTION_KEY` debe ser obligatoria si existen claves encriptadas. Si no está configurada, la app debe negarse a arrancar con un error claro.
- Generar una clave aleatoria en el primer arranque y guardarla en un archivo con permisos restrictivos (ej: `~/.alvora/encryption_key`).
- Documentar la rotación: si la clave se compromete, todas las claves encriptadas deben ser re-encriptadas.

**Fase de aplicación**: 2.

---

### H-3. `POST /api/ai-agent/execute` ejecuta órdenes reales sin idempotencia

**Severidad**: Alta  
**Explotabilidad**: Media (requiere JWT válido pero no aprobación humana).

**Descripción**:  
`routes/ai_agent.py:501-757` ejecuta órdenes reales de compra/venta. El `client_order_id` se genera con `uuid4().hex[:36]` (`execution_engine.py:288`), pero no hay:
- Idempotencia: un retry o doble-click ejecuta dos órdenes.
- `clientOrderId` estable: cambia en cada intento, el broker no puede deduplicar.
- Aprobación humana: `LIVE_CONFIRMATION_REQUIRED=True` en config (línea 78) pero no se valida en la ruta de ejecución.
- Validación de esquema de la salida del LLM: `_parse_response()` hace `json.loads` pero no valida que los campos existan o tengan tipos correctos.

**Corrección propuesta**:  
- Fase 6: `idempotencyKey` por orden, enviado al broker como `newClientOrderId`.
- Fase 5: Risk Engine con veto obligatorio antes de toda ejecución.
- Fase 3: Validación de salida del LLM con JSON Schema.
- Fase 1b: No se cambia la ruta de escritura (fuera de alcance), pero se documenta.

**Fase de aplicación**: 5-6.

---

### H-4. Secretos en el repo (`.env`, `.db`)

**Severidad**: Crítica  
**Explotabilidad**: Alta si el repo es clonado o accedido por terceros.

**Descripción**:  
Los siguientes archivos con secretos o datos sensibles están presentes en el árbol de trabajo:

| Fichero | Contenido |
|---|---|
| `.env` (raíz) | `BROKER_API_KEY`, `BROKER_API_SECRET`, `GROQ_API_KEY`, `GEMINI_API_KEY`, `JWT_SECRET`, etc. |
| `trading-client/.env` | Variables del trading-client |
| `trading.db` | BD SQLite con datos de trading reales |
| `trading.db-shm` / `trading.db-wal` | WAL de SQLite |
| `test.db` | BD de tests |
| `migrations.db` | BD de migraciones |
| `auth-server/alvora_auth.db` | BD del auth-server (si existe) |

**Corrección propuesta**:  
- **Inmediato (manual, fuera del código)**:
  1. Rotar todas las claves expuestas: Binance API key/secret, Groq key, Gemini key, JWT_SECRET.
  2. Añadir `.env`, `*.db`, `*.db-shm`, `*.db-wal` a `.gitignore` si no lo están.
  3. Si el repo fue pushed a un remoto, considerar el historial comprometido. Usar `git filter-repo` o BFG para limpiar el historial.
  4. Revocar y recrear las API keys de Binance desde el panel.
- **Fase 0 (este documento)**: Documentar la exposición.
- **Fase 2**: `ENCRYPTION_KEY` obligatoria (ver H-2).

**Fase de aplicación**: Inmediato (rotación manual) + Fase 2.

---

### H-5. `JWT_SECRET` por defecto y CORS `"*"`

**Severidad**: Alta  
**Explotabilidad**: Alta si el auth-server se despliega con defaults.

**Descripción**:  
`auth-server/app/config.py:25`:
```python
JWT_SECRET: str = "change-me-in-production"
```

`auth-server/app/config.py:35`:
```python
CORS_ORIGINS: str = "*"
```

Si el auth-server se despliega sin override de estas variables, cualquiera puede:
1. Forjar JWTs válidos con `JWT_SECRET="change-me-in-production"`.
2. Hacer requests desde cualquier origen (CORS `"*"`).

**Corrección propuesta**:  
- **Inmediato (manual)**: Cambiar `JWT_SECRET` a un valor aleatorio de 256 bits. Configurar `CORS_ORIGINS` con la URL específica del trading-client.
- **Fase 4**: El ai-server también debe tener su propio `JWT_SECRET` o usar HMAC servicio-a-servicio.
- Validar en startup: si `JWT_SECRET` es el valor por defecto, negarse a arrancar en `APP_ENV != "development"`.

**Fase de aplicación**: Inmediato (configuración) + Fase 4.

---

### H-6. Dinero en `float`

**Severidad**: Media  
**Explotabilidad**: Baja (errores de precisión, no explotación directa).

**Descripción**:  
Múltiples puntos del código usan `float` para dinero y cantidades en lugar de `Decimal`:

| Fichero | Líneas | Uso |
|---|---|---|
| `ai/agent.py` | 224, 237-257, 287, 307, 317 | Trailing stop, PnL, peak tracking |
| `routes/ai_agent.py` | 344, 358-359, 365, 388, 406-417 | Balance, USD value, MXN |
| `routes/trading.py` | 168, 175-178 | Precio live en `/api/positions` |
| `routes/market.py` | 113-117 | Klines como `float` |
| `data/binance_source.py` | 134-138, 186-188 | Parseo de klines y movers |

Esto puede causar:
- Errores de redondeo en trailing stop (ej: vender 0.0000001 BTC de más o de menos).
- Discrepancias entre el saldo mostrado y el real.
- Inconsistencias en PnL calculado.

**Corrección propuesta**:  
- Fase 1b: `adapter.get_ticker()` devuelve `Decimal`; `list_positions()` usa `Decimal`.
- Fase 2: klines y movers en `Decimal`.
- Fase 5: trailing stop en `Decimal` (al mover al Risk Engine).
- Fase 1a: todos los modelos nuevos en `brokers/models.py` usan `Decimal`.

**Fase de aplicación**: 1a-5 (progresivo).

---

### H-7. Sin protección contra prompt injection

**Severidad**: Media  
**Explotabilidad**: Media (requiere que el LLM reciba datos manipulados).

**Descripción**:  
`ai/agent.py:600`:
```python
user_msg = f"Datos:{json.dumps(context,default=str)}\nAnaliza y decide. SOLO JSON."
```

El contexto incluye datos de mercado (movers, precios) que provienen de la API de Binance. Si un símbolo o dato contuviera texto malicioso, se inyectaría directamente en el prompt del LLM. La salida del LLM se ejecuta sin validación de esquema: `_parse_response()` hace `json.loads` pero no valida que `actions` sea una lista, que `type` sea `"buy"` o `"sell"`, etc.

**Corrección propuesta**:  
- Fase 3: Validación de salida con JSON Schema (pydantic model o `jsonschema`).
- Fase 3: Sanitización de inputs: escapar o estructurar los datos de mercado en el prompt.
- Fase 4: El ai-server valida la salida antes de devolverla al cliente.
- Fase 5: Risk Engine con veto independientemente de lo que diga el LLM.

**Fase de aplicación**: 3-5.

---

### H-8. Escritura en `.env` en caliente desde HTTP

**Severidad**: Media  
**Explotabilidad**: Media (requiere JWT válido).

**Descripción**:  
`routes/ai_agent.py:453-485` (`PATCH /ai-agent/capital`) escribe directamente en el archivo `.env`:

```python
# trading-client/app/api/routes/ai_agent.py:464-477
env_path = Path(".env")
if env_path.exists():
    lines = env_path.read_text(encoding="utf-8").splitlines()
    # ... modifica lines ...
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    os.environ["AI_ALLOCATED_CAPITAL"] = str(amount)
```

`routes/ai_agent.py:488-498` (`PATCH /kill-switch`) modifica `os.environ` directamente:

```python
os.environ["LIVE_KILL_SWITCH"] = str(enabled).lower()
```

Problemas:
- Race condition si dos requests modifican `.env` simultáneamente.
- `os.environ` no es persistente entre reinicios (excepto `.env` para capital).
- Un usuario con JWT válido puede modificar la configuración del servidor sin auditoría.

**Corrección propuesta**:  
- Fase 2: Persistir `AI_ALLOCATED_CAPITAL` y `LIVE_KILL_SWITCH` en `user_settings` o en una tabla `system_config`, no en `.env`.
- Fase 5: Kill switch debe ser una operación del Risk Engine con auditoría en `system_events`.

**Fase de aplicación**: 2-5.

---

### H-9. `unsafe { static mut PYTHON_CHILD }` en Tauri

**Severidad**: Baja  
**Explotabilidad**: Baja (race condition teórico en shutdown).

**Descripción**:  
`desktop/src-tauri/src/lib.rs:4`:
```rust
static mut PYTHON_CHILD: Option<Child> = None;
```

`unsafe` se usa para acceder a `PYTHON_CHILD` en `spawn_python_backend` (línea 46) y en el handler `on_window_event` (líneas 70-75). Si Tauri muere abruptamente (crash, kill -9), el proceso Python queda huérfano.

**Corrección propuesta**:  
- Fase 8: Usar `Mutex<Option<Child>>` o `tokio::sync::Mutex` en lugar de `static mut`.
- Registrar el PID en un archivo y verificar al arrancar si hay un proceso huérfano.
- Usar `tauri::async_runtime` para manejar el ciclo de vida.

**Fase de aplicación**: 8.

---

## Plan de Rotación de Claves Expuestas

Las siguientes claves están expuestas en el árbol de trabajo y **deben rotarse manualmente**:

| Clave | Fichero | Acción de rotación |
|---|---|---|
| Binance API Key | `.env` (raíz y `trading-client/.env`) | Revocar desde panel de Binance → crear nueva → actualizar `.env` |
| Binance API Secret | `.env` (raíz y `trading-client/.env`) | Mismo que arriba |
| Groq API Key | `.env` | Revocar desde console.groq.com → crear nueva |
| Gemini API Key | `.env` | Revocar desde Google AI Studio → crear nueva |
| JWT_SECRET | `auth-server/.env` | Generar nuevo secreto de 256 bits → actualizar `.env` del auth-server |
| ENCRYPTION_KEY | No configurada (usa fallback) | Generar clave Fernet aleatoria → configurar `ENCRYPTION_KEY` en `trading-client/.env` → re-encriptar todas las claves en `user_settings` |

> **Importante**: La rotación es una acción manual del usuario. Este documento solo la describe; no la ejecuta.

---

## Lo que NUNCA se envía al AI Server

Esta lista es vinculante para todas las fases:

1. **API keys de broker** (Binance, Bybit, etc.) — nunca.
2. **API secrets de broker** — nunca.
3. **Claves de IA** (Groq, Gemini, etc.) — nunca.
4. **JWT del usuario** — se valida contra el auth-server, pero no se reenvía al ai-server. Se envía un `user_id_hash` (SHA-256 del `sub` del JWT + salt).
5. **Datos personales** (email, username) — nunca. Solo `user_id_hash` y `plan`.
6. **Saldo exacto de la cuenta** — se puede enviar un valor redondeado o categorizado (ej: "cash > 5000") si el usuario lo configura.
7. **Claves de encriptación** — nunca.
8. **Contenido de `.env`** — nunca.
9. **Direcciones de wallet** — nunca.
10. **Historial de órdenes detallado** — solo métricas agregadas (número de posiciones, PnL %).

---

## Resumen por Severidad

| ID | Severidad | Fase |
|---|---|---|
| H-4 | Crítica | Inmediato + Fase 2 |
| H-2 | Alta | Fase 2 |
| H-3 | Alta | Fase 5-6 |
| H-5 | Alta | Inmediato + Fase 4 |
| H-1 | Media | Fase 1b + 3 |
| H-6 | Media | Fase 1a-5 |
| H-7 | Media | Fase 3-5 |
| H-8 | Media | Fase 2-5 |
| H-9 | Baja | Fase 8 |
