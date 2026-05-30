# SDD steps — guía paso a paso

Cómo implementar una feature con el flujo de **Spec-Driven Development** de esta plantilla, con los
comandos exactos y **prompts reales** que puedes copiar/pegar en Claude Code. Incluye cómo empezar en
un proyecto nuevo o en uno con código ya existente.

> Resumen del ciclo (perfil core de OpenSpec). El **plan técnico es obligatorio**, no opcional:
>
> ```
> (explorar/refinar) → /opsx:propose → PLAN TÉCNICO (agentes) → /opsx:apply → PR → /opsx:archive
> ```

---

## 0. Requisitos previos (una vez)

1. Instala el CLI de OpenSpec: `npm i -g @fission-ai/openspec` (o usa `npx @fission-ai/openspec`).
2. **Reinicia Claude Code** para que aparezcan los slash commands `/opsx:*`.
3. Comprueba que todo está: `openspec list` (debe responder sin error).

Las skills (`openspec-*`, `enrich-us`, `write-pr-report`) y los agentes (`backend-developer`,
`frontend-developer`, `product-strategy-analyst`) se autodetectan desde `.claude/`.

---

## 1. Cómo empezar

### 1.A Proyecto nuevo (creado desde esta plantilla)

Todo el andamiaje SDD ya viene incluido. Solo:

```powershell
# tras clonar / "Use this template"
cd backend; uv sync
cd ../frontend; npm install
# regenera las skills/commands para tu versión del CLI (no toca tu código)
openspec update
```

`openspec/specs/` está vacío al principio (es normal): se irá poblando a medida que archives cambios.
El contexto del stack ya está en [openspec/config.yaml](openspec/config.yaml), así que las propuestas
nacen sabiendo que es FastAPI por slices + React por slices.

### 1.B Proyecto con código ya existente

Dos casos:

- **Nació de la plantilla y ya tiene features**: usa el ciclo normal (sección 2) cambio a cambio.
  Opcionalmente crea un *baseline* de specs de lo que ya existe (recomendado) — ver más abajo.
- **Proyecto distinto que adopta este SDD**: copia `.claude/{commands,skills,agents,rules}`,
  `openspec/`, `docs/*-standards.md` y el bloque de `.gitignore`; instala el CLI; ejecuta
  `openspec update`; y **edita [openspec/config.yaml](openspec/config.yaml)** (y los agentes y
  `docs/*-standards.md`) para que describan el stack real de ese proyecto.

**Baseline de specs (opcional pero recomendado en proyectos con código):** captura el comportamiento
actual para tener contra qué comparar los deltas. Prompt de ejemplo:

> Genera el spec OpenSpec del comportamiento ACTUAL de la feature `users` a partir del código en
> `backend/app/features/users/`. Escríbelo en `openspec/specs/users/spec.md` con requisitos y
> escenarios Given/When/Then. No cambies código.

No es obligatorio: también puedes empezar a proponer cambios directamente; los specs se rellenan al archivar.

---

## 2. El ciclo de un cambio (con ejemplo: “CRUD de products solo para admin”)

### Paso 1 — Explorar / refinar (opcional)

Úsalo si la idea es difusa o viene de un ticket.

- Pensar en voz alta sin estructura:

  > /opsx:explore
  >
  > Quiero añadir gestión de productos (listar, crear, editar, borrar) accesible solo por admin.
  > Ayúdame a aclarar alcance, dudas y casos límite antes de proponer el cambio.

- Refinar una user story de **Jira**:

  > Usa la skill `enrich-us` para refinar el ticket PROJ-123.

- Delimitar producto/alcance de algo más abierto:

  > Usa el agente `product-strategy-analyst` para delimitar el alcance de una feature de notificaciones.

### Paso 2 — Crear la propuesta

Genera el cambio con sus artefactos (`proposal.md`, `specs/`, `design.md`, `tasks.md`):

> /opsx:propose añadir CRUD de products (id, sku, nombre, precio, activo) bajo /api/products, solo admin

Resultado: `openspec/changes/add-products/` con los 4 artefactos. El `tasks.md` ya incluye los pasos
obligatorios (rama, pytest, curl, Playwright, lint/test/build, PR) porque están en las reglas del config.

Revisa y ajusta los artefactos si hace falta antes de seguir:

> Revisa `openspec/changes/add-products/specs/` y añade un escenario para el caso de SKU duplicado (409).

### Paso 3 — Plan técnico detallado (OBLIGATORIO)

Antes de implementar, genera el plan a nivel de archivos con los agentes. **Este paso no es opcional**:
`/opsx:apply` debe leer estos planes antes de tocar código.

- Backend:

  > Usa el agente `backend-developer` para crear el plan de implementación del cambio `add-products`.
  > Lee `openspec/changes/add-products/` (proposal, specs, design, tasks) como contexto.
  > Guarda el plan en `.claude/doc/add-products/backend.md`.

- Frontend (si la feature tiene UI):

  > Usa el agente `frontend-developer` para crear el plan de la parte frontend del cambio `add-products`.
  > Guárdalo en `.claude/doc/add-products/frontend.md`.

Cada agente produce un plan capa por capa (router → service → repository → models / api.ts → componentes
→ rutas), incluyendo migración Alembic y tests. **No implementan**: solo planifican.

### Paso 4 — Implementar

> /opsx:apply add-products

Esto:
- Lee los artefactos del cambio **y** los planes técnicos de `.claude/doc/add-products/`.
- Aplica [.claude/rules/openspec-tasks-mandatory-steps.md](.claude/rules/openspec-tasks-mandatory-steps.md):
  crea rama `feature/add-products`, escribe tests, y **el agente ejecuta él mismo** `uv run pytest -q`,
  prueba los endpoints con `curl`, hace E2E con Playwright MCP y corre `npm run lint/test/build`.
- Va marcando las tareas de `tasks.md` solo cuando las pruebas pasan.

Si a mitad descubres que el diseño estaba mal: edita el artefacto (`design.md`/`specs/`), regenera el
plan del agente afectado y continúa. Si surge un fix **después** de apply y antes de archive, primero
actualiza los artefactos OpenSpec (regla 6 de [docs/base-standards.md](docs/base-standards.md)); no
parchees código a pelo.

### Paso 5 — Pull Request

> Usa la skill `write-pr-report` para generar la descripción del PR del cambio `add-products` y créalo con `gh`.

### Paso 6 — Archivar

> /opsx:archive add-products

Fusiona los deltas de `openspec/changes/add-products/specs/` en `openspec/specs/products/` y mueve el
cambio a `openspec/changes/archive/`. A partir de aquí, `openspec/specs/` refleja el nuevo comportamiento.

---

## 3. Comandos CLI útiles (terminal)

```powershell
openspec list                       # cambios activos
openspec show add-products          # ver un cambio
openspec status --change add-products   # progreso de artefactos
openspec validate --all             # validar specs/cambios
openspec new change <nombre>        # crear el andamiaje de un cambio desde la terminal
```

---

## 4. Checklist mental por feature

1. (Opcional) `explore` / `enrich-us` / `product-strategy-analyst`.
2. `/opsx:propose` → artefactos creados y revisados.
3. **Plan técnico con agentes** → `.claude/doc/<cambio>/{backend,frontend}.md` (OBLIGATORIO).
4. `/opsx:apply` → implementación + verificación que ejecuta el agente.
5. `write-pr-report` + `gh` → PR.
6. `/opsx:archive` → specs fusionadas.

Ver también: [docs/development_guide.md](docs/development_guide.md), [docs/verification-guide.md](docs/verification-guide.md),
[docs/base-standards.md](docs/base-standards.md).
