## Context

El repo es un backend FastAPI puro (sin frontend). Los archivos copiados desde FastAPI Template asumen una estructura monorepo con `backend/` subfolder, `frontend/` y Caddy. Hay tres categorías de trabajo:

1. **Config/docs**: archivos de documentación y configuración que referencian rutas y stacks inexistentes en este proyecto.
2. **Código backend**: mejoras del template ya aplicadas en el working tree (auth lockout, rate limiting, roles delete, validaciones users), pero incompletas: falta la dependencia `slowapi` en `pyproject.toml`, falta registrar el limiter en la app, falta la migración Alembic para los nuevos campos del modelo `User`, y `settings.py`/`main.py` aún referencian el frontend.
3. **Nombre del proyecto**: `pyproject.toml` dice `fastapi-template`; conviene actualizarlo.

---

## Goals / Non-Goals

**Goals:**
- Adaptar `CLAUDE.md` y `openspec/config.yaml` para reflejar la estructura real (backend plano, sin frontend).
- Eliminar o corregir referencias a frontend en `docs/` y en código.
- Completar la integración de SlowAPI: añadir dependencia, registrar middleware y handler en `main.py`.
- Crear migración Alembic para `failed_login_attempts` y `locked_until` en `User`.
- Verificar que todos los cambios de código del template (auth, users, roles) son coherentes y los tests pasan.

**Non-Goals:**
- No introducir ninguna funcionalidad nueva más allá de lo que trajo el template.
- No tocar el slice `butler` (lógica específica de este proyecto).
- No añadir frontend ni Docker Caddy.

---

## Decisions

### Decisión 1: Integrar SlowAPI como state en FastAPI (no como middleware global)

SlowAPI requiere que `app.state.limiter = limiter` y un exception handler para `RateLimitExceeded`. Se registra en `create_app()` en `main.py`, no en `lifespan.py` (que es para dependencias de BD). El decorador `@limiter.limit(...)` en los routers ya funciona.

```python
# main.py
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.limiter import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

**Alternativa considerada**: middleware global (`SlowAPIMiddleware`). Descartada porque no encaja bien con los decoradores de ruta ya existentes y añade overhead innecesario para una API sin tráfico masivo.

### Decisión 2: Eliminar `frontend_url` y `frontend_dist_dir` de `settings.py`

Estos campos sirven solo para servir la SPA del frontend. Al no haber frontend, los eliminamos. La sección de CORS en `main.py` se simplifica para permitir solo los orígenes que necesite Minecraft/el cliente real (por ahora, orígenes de desarrollo).

### Decisión 3: Migración Alembic para campos de lockout

Los campos `failed_login_attempts` (Integer, default 0, server_default "0", NOT NULL) y `locked_until` (DateTime, nullable) se añaden a la tabla `users`. La migración es no destructiva (solo ADD COLUMN con defaults); no requiere downtime.

### Decisión 4: Adaptar docs, no eliminar la mayoría

- `docs/frontend-standards.md`: eliminar (cero relevancia).
- `docs/base-standards.md`: eliminar la mención a `frontend-standards.md`.
- `docs/backend-standards.md`: corregir rutas `backend/app/...` → `app/...`.
- `docs/development_guide.md`: eliminar secciones de frontend y comandos `cd backend`.
- `docs/verification-guide.md`: eliminar pasos de frontend (`npm run lint/test/build`).
- El resto de `docs/` (data-model, documentation-standards, SDD steps): revisar puntualmente.

---

## Riscos / Trade-offs

- [Migración en producción] Si la BD ya tiene filas en `users`, `ADD COLUMN ... DEFAULT 0` es seguro en PostgreSQL (operación online, no bloquea). Mitigación: confirmar con `SELECT COUNT(*) FROM users` antes de aplicar.
- [SlowAPI y rate limiting en desarrollo] Por defecto SlowAPI usa IP remota. Detrás de un proxy se necesita `X-Forwarded-For`. Mitigación: documentar en `docs/` si se despliega con proxy; por ahora el proyecto no usa proxy.
- [pydantic-email-validator] `EmailStr` en `users/schemas.py` requiere `pydantic[email]` (o `email-validator`). Verificar que la dependencia está disponible en el entorno.

---

## Migration Plan

1. Crear rama `feature/sync-template-to-backend`.
2. Adaptar archivos de config/docs (sin tocar código).
3. Completar código backend: `pyproject.toml` (añadir `slowapi`, `email-validator`), `settings.py`, `main.py`.
4. Generar y aplicar migración Alembic.
5. Ejecutar `uv run pytest -q` en verde.
6. Pruebas manuales con curl.
7. PR y archive.

**Rollback**: los cambios de config/docs no afectan BD. La migración Alembic se revierte con `alembic downgrade -1` si fuera necesario.

---

## Open Questions

- ¿Se mantiene el CORS abierto a `localhost:5173` en desarrollo (Minecraft client no es un browser)? Probablemente se puede eliminar o reducir los orígenes CORS, pero se deja como documentación por si se añade un cliente web en el futuro.
