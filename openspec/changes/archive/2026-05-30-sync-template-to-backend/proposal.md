## Why

Se han copiado los archivos actualizados de FastAPI Template (monorepo con `backend/` + `frontend/` + Caddy) a este proyecto, que es solo backend sin frontend. El traspaso dejó archivos de configuración y documentación que referencian rutas y stacks inexistentes (frontend, `backend/` subfolder), y code changes del template que incluyen mejoras de seguridad que deben verificarse y completarse (migración Alembic pendiente, `limiter` no registrado en la app, configuración no adaptada).

## What Changes

**Adaptaciones de configuración y documentación:**
- `CLAUDE.md`: eliminar toda sección de frontend y monorepo; adaptar rutas y comandos a la estructura plana de este proyecto.
- `openspec/config.yaml`: eliminar referencias a `backend/` y `frontend/`; reflejar el stack real (solo Python/FastAPI en raíz).
- `docs/frontend-standards.md`: eliminar (irrelevante para este proyecto).
- `docs/backend-standards.md`, `docs/development_guide.md`, `docs/verification-guide.md`: corregir rutas que asumen `backend/` subfolder.

**Completar las mejoras de código del template:**
- `app/core/settings.py`: eliminar `frontend_url` y `frontend_dist_dir` (sin frontend); conservar `validate_production_secrets`.
- `app/main.py`: eliminar montaje de assets estáticos del frontend (`StaticFiles`).
- Crear migración Alembic para los campos nuevos en `User`: `failed_login_attempts` (Integer, default 0) y `locked_until` (DateTime, nullable).
- Registrar `SlowAPI` limiter en `app/core/lifespan.py` y el middleware en `app/main.py` (actualmente `limiter.py` existe pero no está conectado a la app).

**Mejoras ya aplicadas en código (verificar integridad):**
- `auth/router.py`: rate limiting 10/min en login/token, 20/min en refresh.
- `auth/service.py`: bloqueo de cuenta tras 5 intentos fallidos (15 min).
- `auth/security.py`: `exp` del JWT como timestamp entero.
- `roles/`: endpoint `DELETE /api/roles/{role_id}` con protección de roles de sistema.
- `users/`: validación más estricta (email, contraseñas ≥ 8 chars, patrón de username); `is_locked`/`locked_until` en respuestas.

## Capabilities

### New Capabilities
- `api-rate-limiting`: Rate limiting en endpoints de autenticación mediante SlowAPI.
- `account-lockout`: Bloqueo temporal de cuenta tras intentos de login fallidos.

### Modified Capabilities
- `auth`: Nuevos escenarios de bloqueo de cuenta y rate limiting en login/refresh.
- `users`: Validación reforzada de username/password/email; campos `is_locked` y `locked_until` en respuestas.
- `roles`: Nuevo endpoint `DELETE /api/roles/{role_id}` con protección de roles de sistema.

## Impact

- **Modelo de datos**: requiere migración Alembic — campos `failed_login_attempts` y `locked_until` en tabla `users`.
- **Backend slices afectados**: `app/core/` (settings, lifespan, limiter), `app/features/auth/`, `app/features/users/`, `app/features/roles/`.
- **Dependencias**: `slowapi` (ya presente en el código; verificar que está en `pyproject.toml`).
- **Documentación**: `CLAUDE.md`, `openspec/config.yaml`, `docs/` (varios archivos).
- **Sin cambios en frontend** (este proyecto no tiene frontend).
