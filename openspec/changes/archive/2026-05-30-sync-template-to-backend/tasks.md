## 0. Setup (OBLIGATORIO - PRIMER PASO)

- [x] 0.1 Crear rama `feature/sync-template-to-backend` desde main

## 1. Documentación y configuración (adaptación al proyecto)

- [x] 1.1 Adaptar `CLAUDE.md`: eliminar sección de frontend y monorepo, corregir estructura a proyecto plano (sin `backend/` subfolder), actualizar comandos (`uv run pytest -q` sin `cd backend`, sin comandos npm)
- [x] 1.2 Adaptar `openspec/config.yaml`: eliminar referencias a `backend/` y `frontend/`; reflejar stack real (Python/FastAPI en raíz, sin frontend)
- [x] 1.3 Eliminar `docs/frontend-standards.md` (irrelevante, sin frontend)
- [x] 1.4 Corregir `docs/backend-standards.md`: cambiar rutas `backend/app/...` → `app/...` y `backend/tests/` → `tests/`
- [x] 1.5 Corregir `docs/development_guide.md`: eliminar secciones de frontend y quitar `cd backend` de los comandos
- [x] 1.6 Corregir `docs/verification-guide.md`: eliminar pasos de frontend (npm lint/test/build, E2E)
- [x] 1.7 Corregir `docs/base-standards.md`: eliminar referencia a `frontend-standards.md`
- [x] 1.8 Actualizar `pyproject.toml`: cambiar `name` a `minecraftbutlerai-backend`; añadir `slowapi` y `email-validator` a `dependencies`

## 2. Backend core — completar integración del template

- [x] 2.1 Eliminar `frontend_url` y `frontend_dist_dir` de `app/core/settings.py`; conservar `validate_production_secrets` y `is_production`
- [x] 2.2 Actualizar `app/main.py`: eliminar `StaticFiles` y el montaje de assets del frontend; registrar `app.state.limiter = limiter` y `app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)`
- [x] 2.3 Verificar `app/features/auth/router.py`: `@limiter.limit` en los tres endpoints; `Request` presente en las firmas
- [x] 2.4 Verificar `app/features/auth/service.py`: lógica de lockout coherente (`_MAX_FAILED_ATTEMPTS=5`, `_LOCKOUT_MINUTES=15`); import de `timedelta` en el lugar correcto (no dentro de la clase)
- [x] 2.5 Verificar `app/features/users/schemas.py`: `EmailStr` importado, `_USERNAME_PATTERN` aplicado, limits de password (8-128 chars) en todas las requests

## 3. Migración Alembic — campos de lockout en User (OBLIGATORIO)

- [x] 3.1 Capturar baseline de BD: conteo de filas en tabla `users`
- [x] 3.2 Generar migración Alembic: `uv run alembic revision --autogenerate -m "add_user_lockout_fields"`; revisar el script generado para confirmar que añade `failed_login_attempts` (Integer, default 0, server_default "0", NOT NULL) y `locked_until` (DateTime, nullable)
- [x] 3.3 Aplicar migración: `uv run alembic upgrade head`; verificar que el conteo de filas no cambió y los nuevos campos existen en la BD

## 4. Tests de backend (OBLIGATORIO)

- [x] 4.1 Ejecutar `uv run pytest -q` y confirmar que todos los tests pasan en verde
- [x] 4.2 Verificar el estado de la BD post-test (conteo de usuarios y roles igual al baseline)
- [x] 4.3 Guardar informe en `openspec/changes/sync-template-to-backend/reports/YYYY-MM-DD-backend-tests.md` con comandos, resultados y comparación pre/post BD

## 5. Pruebas manuales de endpoints con curl (OBLIGATORIO - EL AGENTE LO EJECUTA)

- [x] 5.1 Arrancar el backend: `uv run uvicorn app.main:app --reload`
- [x] 5.2 **Auth — login y lockout**: GET /api/health (200); POST /api/auth/login con credenciales válidas (200); POST /api/auth/login con credenciales inválidas 5 veces seguidas (4× 401, la 5ª da 429 bloqueado); login con cuenta bloqueada (429); esperar expiración o resetear campo manualmente y login exitoso
- [x] 5.3 **Auth — JWT y rate limiting**: verificar que el `exp` del token decodificado es un entero UNIX timestamp; hacer 11 peticiones a /api/auth/login en un minuto y confirmar 429 en la undécima
- [x] 5.4 **Roles — DELETE**: POST /api/auth/login para obtener token admin; DELETE /api/roles/{id_no_sistema} (204); DELETE /api/roles/{id_admin} (400 "No se puede eliminar un rol del sistema"); DELETE /api/roles/99999 (404)
- [x] 5.5 **Users — validaciones**: POST /api/users con `username="ab"` (422); con `password="1234567"` (422); con `email="invalid"` (422); con payload válido (201)
- [x] 5.6 **Verificar campos locked en respuesta**: GET /api/users (200, lista incluye `is_locked` y `locked_until`)
- [x] 5.7 Restaurar el estado de la BD: eliminar usuarios de prueba creados; desbloquear cuentas si aplica
- [x] 5.8 Documentar comandos y respuestas en el informe de reports/

## 6. Cierre (OBLIGATORIO)

- [x] 6.1 Actualizar `docs/data-model.md` si los nuevos campos `failed_login_attempts` y `locked_until` no están documentados
- [x] 6.2 Abrir PR con `gh` usando la skill `write-pr-report` (descripción generada; pendiente de remote git para gh pr create)
