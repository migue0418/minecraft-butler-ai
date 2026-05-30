# Guía de desarrollo

Cómo arrancar y trabajar en MinecraftButlerAI Backend, y cómo usar el flujo SDD (OpenSpec).

## Requisitos

- Docker (para Postgres y/o todo el stack), **uv** (backend).
- **OpenSpec CLI** para el flujo SDD: `npm i -g @fission-ai/openspec` (o usar `npx @fission-ai/openspec`).

## Arrancar

### Todo con Docker
```powershell
docker compose up --build
```

### Backend en local (requiere uv)
```powershell
uv sync                                  # crea .venv e instala deps + dev
uv run uvicorn app.main:app --reload
```

## Dependencias del backend (uv)
```powershell
uv add <paquete>        # producción
uv add --dev <paquete>  # solo dev/test
uv lock                 # regenerar lock file
```
No instales dependencias sin confirmación del usuario.

## Variables de entorno

- Copia `.example.env` a `.env`. La configuración se lee vía `app.core.settings.get_settings()`. Nunca commitees secretos.

## Flujo SDD con OpenSpec (perfil core)

Guía detallada con prompts reales: **[docs/SDD steps.md](./SDD%20steps.md)**.

```
/opsx:explore        → pensar/aclarar una idea (opcional)
/opsx:propose        → crear el cambio y sus artefactos (proposal, specs, design, tasks)
plan técnico         → agente backend-developer (OBLIGATORIO, → .claude/doc/<cambio>/backend.md)
/opsx:apply          → implementar las tareas (el agente ejecuta también las pruebas)
write-pr-report + gh → abrir el PR
/opsx:archive        → fusionar los delta specs en openspec/specs/ y archivar el cambio
```

- Antes de `/opsx:apply` DEBE existir el plan técnico del agente en `.claude/doc/<cambio>/backend.md`; no es opcional.
- Antes de escribir/implementar `tasks.md`, se aplica `.claude/rules/openspec-tasks-mandatory-steps.md`.
- Contexto del stack inyectado en todos los artefactos: `openspec/config.yaml`.
- Comandos CLI útiles: `openspec list`, `openspec show <c>`, `openspec validate --all`, `openspec status --change <c>`.

### Agentes y skills de apoyo
- Agentes de planificación (`.claude/agents/`): `backend-developer` (plan técnico obligatorio), `product-strategy-analyst` (ideación/refinamiento).
- Skills (`.claude/skills/`): `enrich-us` (refinar user stories de Jira), `write-pr-report` (descripción de PR + `gh`).

## Verificación

Ver [guía de verificación](./verification-guide.md). Resumen:
```powershell
uv run pytest -q
```

## Qué NO hacer

- No usar SQLite en tests del backend (usar PostgreSQL).
- No duplicar lógica de negocio.
- No hacer cambios grandes no relacionados con la petición.
