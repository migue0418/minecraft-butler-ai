# Informe de tests y verificación — derive-session-id-from-user

Fecha: 2026-06-05
Rama: `feature/derive-session-id-from-user` (desde `main`)

## Alcance
Derivar el `thread_id` del usuario autenticado (`user-{id}`) cuando no llega `session_id`, para
dar memoria conversacional persistente por defecto. Toca `service.py` y `router.py` del slice
`butler`. Sin BD.

## Estado de la BD
**Sin mutación de la BD relacional.** La memoria vive en Redis (checkpointer) con su TTL. Sin
modelos ni migraciones. No procede baseline ni restauración de BD.

## Tests unitarios (TDD)
- `test_resolve_thread_id.py`: precedencia `session_id` → `user-{id}` → `ephemeral-…`.
  Pre-implementación: ROJO (`_resolve_thread_id` no existía). Post: verde.
- `test_service_stream.py`: `stream(..., user_id=7)` sin session_id usa `thread_id="user-7"`;
  `stream(..., session_id="s1", user_id=7)` usa `"s1"` (precedencia). Pre: ROJO. Post: verde.

Suite completa:
```
uv run pytest -q
→ 135 passed, 8 warnings   (8 warnings preexistentes de SlowAPI)
```
Los tests de streaming/servicio existentes (que llaman sin `user_id`) siguen en verde gracias al
default `user_id=None`.

## Verificación con curl en vivo (EL AGENTE LO EJECUTA) — puerto 8015

Usuario admin (`user_id=1`).

### Memoria por usuario SIN session_id (el arreglo)
```
Turno 1 (sin session_id): "Recuerda esto: me llamo Bartolo."  → "Entendido, Bartolo."
Turno 2 (sin session_id): "Como me llamo?"                     → "Te llamas Bartolo."
```
Antes de este cambio el turno 2 olvidaba (hilo efímero por petición). Ahora recuerda.

Redis tras los dos turnos:
```
checkpoint:user-1:*  → 8 claves   (hilo persistente derivado del usuario)
```

### Precedencia del session_id explícito
```
POST /ask con session_id="mundo-creativo"  → checkpoint:mundo-creativo:* (4 claves)
```
Con `session_id` explícito se usa ese id, no `user-1`. Precedencia correcta.

## Conclusión
- Memoria conversacional persistente por usuario cuando no se envía `session_id` (verificada en
  vivo + Redis).
- `session_id` explícito mantiene su precedencia (aislamiento de conversaciones a medida).
- Suite completa en verde (135), sin mutación de la BD relacional.
