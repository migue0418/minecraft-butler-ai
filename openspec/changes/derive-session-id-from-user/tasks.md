## 0. Setup (OBLIGATORIO - PRIMER PASO)

- [x] 0.1 Crear y cambiar a la rama `feature/derive-session-id-from-user` **desde `main`**
- [x] 0.2 Plan técnico breve en `.claude/doc/derive-session-id-from-user/backend.md` (`/opsx:apply` debe leerlo)

## 1. Backend: tests (TDD)

- [x] 1.1 Test unitario de `_resolve_thread_id(session_id, user_id)`: devuelve `session_id` si viene; `user-{id}` si no hay session_id pero sí user; `ephemeral-…` si no hay ninguno
- [x] 1.2 Test de integración (TestClient): dos peticiones a `/api/butler/ask` del mismo usuario **sin** `session_id` resuelven al mismo `thread_id` y el grafo recibe el historial acumulado (mockear el grafo/LLM; verificar el `thread_id` del `config` o el estado acumulado)
- [x] 1.3 Test: una petición **con** `session_id` explícito sigue usando ese id (precedencia), no el del usuario
- [x] 1.4 Ejecutar los tests y confirmar que fallan (rojo) contra el código actual

## 2. Backend: implementación (slice butler)

- [x] 2.1 En `app/features/butler/service.py`: helper `_resolve_thread_id(session_id, user_id)` con la precedencia session_id → `user-{id}` → `ephemeral-{uuid4}`. Usarlo en `run()` y en `_run_graph_to_queue()`
- [x] 2.2 Añadir parámetro `user_id: int | None = None` a `run()` y `stream()` (y propagarlo a `_run_graph_to_queue()`); incluir `user_id` en el `metadata` del run de streaming
- [x] 2.3 En `app/features/butler/router.py`: renombrar `_user` → `user` y pasar `user_id=user.id` en los 4 endpoints (`ask`, `ask_voice`, `ask_stream`, `ask_voice_stream`)

## 3. Backend: tests y estado de BD (OBLIGATORIO)

- [x] 3.1 `uv run pytest -q` en verde (suite completa). El cambio NO muta la BD relacional; la memoria vive en Redis. Sin baseline ni restauración de BD. Dejar constancia en el informe
- [x] 3.2 Guardar informe en `openspec/changes/derive-session-id-from-user/reports/YYYY-MM-DD-backend-tests.md`

## 4. Backend: endpoints con curl (OBLIGATORIO - EL AGENTE LO EJECUTA)

- [x] 4.1 Arrancar el backend con servicios disponibles (PostgreSQL, Redis, Qdrant)
- [x] 4.2 Dos turnos en `/api/butler/ask` **sin** `session_id` con el mismo token: turno 1 "recuerda esto: me llamo X", turno 2 "¿cómo me llamo?" → debe responder "X" (memoria por usuario)
- [x] 4.3 Verificar en Redis que aparece un hilo `checkpoint:user-{id}:…` (y ya no solo efímeros) para ese usuario
- [x] 4.4 Confirmar que con `session_id` explícito se usa ese id (precedencia) y que dos usuarios distintos quedan aislados
- [x] 4.5 Documentar comandos y respuestas en el informe del cambio

## 5. Cierre (OBLIGATORIO)

- [x] 5.1 Actualizar `docs/` y la nota de memoria conversacional en `ARCHITECTURE.md` (sesión por usuario por defecto)
- [x] 5.2 Generar la descripción del PR con la skill `write-pr-report` y abrir el PR con `gh pr create`
