# Informe de tests — sync-template-to-backend — 2026-05-30

## Comando ejecutado
```
uv run pytest -q
```

## Resultado
```
14 passed, 3 warnings in 6.93s
```
✅ Todos los tests en verde.

## Issues encontrados y resueltos durante la ejecución

### 1. Rate limiting en tests (429 en login)
- **Causa**: `limiter` es un singleton de módulo cuyo `MemoryStorage` persiste entre tests. Tras 10 llamadas a `/api/auth/login` en la misma ejecución, el rate limiter devuelve 429.
- **Solución**: Llamar a `limiter._storage.reset()` al inicio de cada fixture `build_client`, antes de crear el `TestClient`.

### 2. DuplicateTableError en `test_legacy_schema_is_migrated_and_seeded`
- **Causa**: `_seed_legacy_schema` creaba la tabla `users` directamente. Luego la migración 0001 intentaba crear esa misma tabla → `DuplicateTableError`.
- **Solución**: Reescribir `_seed_legacy_schema` para crear el schema completo equivalente a la revisión 0001 (todos los tables, índices y la constraint unique de `user_roles`) + estampar `alembic_version` a `'0001'`. De esta forma Alembic solo ejecuta la migración 0002 (lockout fields).

## Pruebas manuales con curl (2026-05-30)

### Health
```
GET /health → 200 {"status":"ok"}
```

### Auth — login y lockout
- `POST /api/auth/login` con credenciales correctas → **200** con `access_token`
- 4 intentos con password incorrecta → **401** "Credenciales invalidas" (incrementa `failed_login_attempts`)
- 5º intento → **401** (se establece `locked_until = now + 15min`)
- 6º intento (cuenta bloqueada, incluso con password correcta) → **429** `"Cuenta temporalmente bloqueada. Inténtalo de nuevo más tarde"`

### JWT exp como entero
- `exp` en el JWT decodificado es `int` (ej: `1780128354`) ✅

### Roles — DELETE
- `DELETE /api/roles/{id_no_sistema}` → **204** ✅
- `DELETE /api/roles/1` (admin, rol del sistema) → **400** `"No se puede eliminar un rol del sistema"` ✅
- `DELETE /api/roles/99999` → **404** `"Rol no encontrado"` ✅

### Users — validaciones
- `POST /api/users` con `username="ab"` → **422** (min_length: 3) ✅
- `POST /api/users` con `password="1234567"` → **422** (min_length: 8) ✅
- `POST /api/users` con `email="notanemail"` → **422** (invalid email) ✅
- `POST /api/users` payload válido → **201** con `is_locked=false, locked_until=null` ✅

### Campos locked en respuestas
- `GET /api/users` → todos los usuarios incluyen `is_locked` y `locked_until` ✅

### Restauración
- Usuario de prueba `testuser` eliminado vía `DELETE /api/users/{id}` → **204**
- Estado final: `users=1, roles=2` (igual al baseline)

## Estado de BD pre/post test
- BD de producción `minecraftbutlerai`: 0 usuarios, 0 roles (no mutada)
- Los tests usan BDs efímeras propias (prefijo `autorecambios_test_*`) que se crean y eliminan automáticamente
