---
description: Pasos obligatorios al crear tasks.md y al implementar un cambio OpenSpec. El agente ejecuta las pruebas él mismo; nunca las delega.
alwaysApply: true
---

# OpenSpec: pasos obligatorios en tasks.md e implementación

Aplica al crear/actualizar `tasks.md` (vía `/opsx:propose` o `openspec-propose`) y al implementar
(vía `/opsx:apply` o `openspec-apply-change`). Complementa `openspec/config.yaml` (lee su `rules.tasks`).

## 0. Plan técnico previo (OBLIGATORIO, antes de `/opsx:apply`)

Antes de implementar un cambio DEBE existir un **plan técnico a nivel de archivos**, generado por los
agentes de planificación y guardado en `.claude/doc/<change-name>/`:

- Agente `backend-developer` → `.claude/doc/<change-name>/backend.md` (si el cambio toca backend).
- Agente `frontend-developer` → `.claude/doc/<change-name>/frontend.md` (si el cambio toca frontend).

`/opsx:apply` (y la skill `openspec-apply-change`) DEBEN **leer esos planes** además de los artefactos
del cambio antes de tocar código. Si el plan no existe, créalo primero con el agente correspondiente; no
empieces a implementar sin él. El plan se escala al tamaño del cambio (en cambios triviales, breve).

## 1. Estructura obligatoria de `tasks.md`

- **Paso 0 (el primero):** crear y cambiar a rama `feature/<change-name>`.
- **TDD** donde tenga sentido: primero tests que fallan, luego implementación.
- Incluye SIEMPRE, además del trabajo funcional, estos pasos marcados `(OBLIGATORIO)`:
  - Revisar/actualizar tests unitarios afectados.
  - Ejecutar tests de backend y verificar estado de BD.
  - Pruebas manuales de endpoints con curl **(EL AGENTE LO EJECUTA)**.
  - E2E con Playwright MCP **(EL AGENTE LO EJECUTA, si hay cambios de frontend)**.
  - Verificación de frontend (`lint` + `test` + `build`).
  - Actualizar documentación técnica en `docs/`.
  - Abrir PR con `gh` (skill `write-pr-report`).

## 2. El agente ejecuta las pruebas — nunca las delega

**CRÍTICO:** el agente (IA) DEBE ejecutar él mismo todas las pruebas manuales. **Nunca** pidas
al usuario que ejecute curl, tests o E2E. Una tarea solo se marca `[x]` tras ejecutar y verificar.

### Tests de backend y estado de BD (OBLIGATORIO)
1. Asegura servicios disponibles (PostgreSQL en marcha; **nunca SQLite** en tests).
2. Captura baseline de BD relevante (conteos, registros clave) si el cambio muta datos.
3. Ejecuta tests dirigidos del módulo y luego la suite: `cd backend && uv run pytest -q`.
4. Verifica el estado de BD post-test; restaura si hubo mutaciones.
5. Guarda informe en `openspec/changes/<change-name>/reports/YYYY-MM-DD-backend-tests.md`
   (comandos, resultados, comparación pre/post BD, acciones de restauración).

### Pruebas de endpoints con curl (OBLIGATORIO para endpoints nuevos/cambiados)
1. Arranca el backend si hace falta (`cd backend && uv run uvicorn app.main:app --reload`).
2. Prueba GET / POST / PUT|PATCH / DELETE con `curl` y verifica códigos (200, 201, 204, 400, 401/403, 404, 409, 422) y cuerpos.
3. Tras CREATE/UPDATE/DELETE, **restaura el estado de la BD** al original.
4. Prueba casos de error (validación, no autorizado, inexistente).
5. Documenta comandos y respuestas en el informe del cambio.

### E2E con Playwright MCP (OBLIGATORIO si hay cambios de frontend)
1. Arranca frontend y backend.
2. Usa las herramientas Playwright MCP (`browser_navigate`, `browser_click`, `browser_type`, `browser_snapshot`...) para recorrer el flujo de usuario completo y los casos de error.
3. Verifica persistencia de datos y estado de la UI; restaura datos de prueba al terminar.

### Verificación de frontend (OBLIGATORIO si hay cambios de frontend)
- `cd frontend && npm run lint && npm run test && npm run build` debe pasar.

## 3. Cierre del cambio
- Actualiza `docs/` si cambian contratos de API, modelo de datos o arquitectura.
- Genera la descripción del PR con la skill `write-pr-report` y créalo con `gh pr create`.
- Solo entonces procede `/opsx:archive` (que fusiona los delta specs en `openspec/specs/`).

## 4. Checklist antes de finalizar `tasks.md`
- [ ] Existe el plan técnico previo en `.claude/doc/<change-name>/` (backend y/o frontend) y `apply` lo ha leído.
- [ ] Paso 0 de tasks.md (rama `feature/<change-name>`) es el primero.
- [ ] Todos los pasos `(OBLIGATORIO)` presentes y numerados.
- [ ] Pruebas manuales marcadas "EL AGENTE LO EJECUTA".
- [ ] Pasos de restauración de BD incluidos para operaciones que mutan datos.
- [ ] Paso E2E incluido si hay cambios de frontend.
- [ ] Paso de actualización de `docs/` y de PR (`gh` + write-pr-report).

## 5. Ejemplo de estructura

```markdown
## 0. Setup (OBLIGATORIO - PRIMER PASO)
- [ ] 0.1 Crear rama `feature/<change-name>` desde main/master

## 1. Backend: <slice> (TDD)
- [ ] 1.1 Tests del repository/service (pytest)
- [ ] 1.2 models.py + migración Alembic (si aplica) + registro en import_model_modules
- [ ] 1.3 repository.py / service.py / schemas.py / router.py + registro en main.py

## 2. Frontend: <feature> (si aplica)
- [ ] 2.1 types.ts + api.ts (envolviendo api.*) + componentes + rutas

## 3. Backend: tests y estado de BD (OBLIGATORIO)
- [ ] 3.1 `cd backend && uv run pytest -q` en verde; baseline/verify BD; informe en reports/

## 4. Backend: endpoints con curl (OBLIGATORIO - EL AGENTE LO EJECUTA)
- [ ] 4.1 GET/POST/PUT/DELETE + casos de error; restaurar BD; documentar

## 5. Frontend: E2E Playwright MCP (OBLIGATORIO si aplica - EL AGENTE LO EJECUTA)
- [ ] 5.1 Flujo completo + errores; restaurar datos

## 6. Frontend: verificación (OBLIGATORIO si aplica)
- [ ] 6.1 `npm run lint && npm run test && npm run build`

## 7. Cierre (OBLIGATORIO)
- [ ] 7.1 Actualizar docs/ afectadas
- [ ] 7.2 PR con gh (write-pr-report)
```

**Si implementas sin ejecutar tú mismo las pruebas manuales, estás violando esta regla.**
