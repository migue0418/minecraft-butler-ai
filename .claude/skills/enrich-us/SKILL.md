---
name: enrich-us
description: Analiza y enriquece user stories de Jira con el detalle técnico necesario para implementarlas de forma autónoma en esta plantilla (FastAPI por slices + React por slices). Úsala cuando el usuario quiera refinar/enriquecer un ticket de Jira antes de planificar o crear una propuesta OpenSpec.
author: adaptado de LIDR.co
version: 1.0.0
---

# enrich-us Skill

Enriquece una user story de Jira hasta dejarla lista para implementar (y para alimentar `/opsx:propose`).

## Instrucciones

Analiza y mejora el ticket de Jira: $ARGUMENTS.

Sigue estos pasos:

1. **Localiza el ticket** con el MCP de Jira: por id/clave, por palabras clave, o por estado
   (p. ej. "el que está en progreso"). Si hay ambigüedad, pregunta.
2. Actúa como **experto de producto con conocimiento técnico** de esta plantilla.
3. **Entiende el problema** descrito en el ticket.
4. Decide si la user story está completa según buenas prácticas: descripción funcional completa,
   lista de campos afectados, estructura y URLs de endpoints (siempre bajo `/api/...`), archivos a
   modificar **según la arquitectura por slices** (`backend/app/features/<feature>/{router,schemas,service,repository,models}.py`
   y, en frontend, `frontend/src/features/<feature>/{types.ts,api.ts,componentes}` + rutas), si
   requiere **migración Alembic**, criterios de "hecho" (Definition of Done), tests a crear
   (pytest en backend, Vitest en frontend) y documentación a actualizar (`docs/`), más requisitos
   no funcionales (seguridad, rendimiento, autorización por roles).
5. Si le falta detalle para que un desarrollador sea autónomo, **reescribe la story** más clara,
   específica y concisa, alineada con el paso 4 y con el contexto técnico de `docs/base-standards.md`,
   `docs/backend-standards.md` y `docs/frontend-standards.md`. Devuélvela en Markdown.
6. **Guarda** la story enriquecida en `tmp/<ticket-id>-enriched-us.md` (crea `tmp/` si no existe;
   ya está en `.gitignore`).
7. **Actualiza el ticket en Jira** añadiendo el nuevo contenido tras el original, marcando cada
   sección con encabezados h2 `[original]` y `[enhanced]`. Usa formato legible (listas, snippets).
8. Respeta el flujo de columnas del tablero si el ticket tiene un estado de refinamiento definido
   (mueve a la columna de validación de refinamiento si existe esa convención en el proyecto).

> Nota: el detalle técnico debe ser fiel al stack real. No propongas patrones ajenos (DDD por capas,
> ORM distinto de SQLAlchemy, `fetch` directo en componentes, SQLite en tests): sigue los estándares
> del template.
