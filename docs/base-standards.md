# Estándares base

Reglas de desarrollo de este proyecto, aplicables a cualquier agente IA y a la persona desarrolladora.
Es la referencia versionada que viaja con la plantilla. `CLAUDE.md` es el resumen rápido local.

## 1. Principios

- **Pasos pequeños, uno a uno.** Cambios incrementales y enfocados; evita modificaciones grandes y mezcladas.
- **TDD donde aporte.** Empieza por tests que fallan para nueva funcionalidad, según el detalle de la tarea.
- **Tipado.** Backend con type hints y Pydantic.
- **Nombres claros y descriptivos** para variables, funciones y archivos.
- **Cuestiona supuestos** y detecta patrones repetidos antes de abstraer (3 líneas parecidas mejor que una abstracción prematura).
- **No metas funcionalidad de más** ni manejo de errores para escenarios imposibles. Valida en los bordes (entrada de usuario, APIs externas).

## 2. Idioma

- **Mensajes de usuario y `detail` de errores en español** (coherente con el código actual del template).
- **Identificadores de código en inglés** (variables, funciones, clases, módulos).
- Documentación del proyecto: español.

## 3. Estándares específicos

- [Estándares de backend](./backend-standards.md) — FastAPI async por slices, datos, auth, tests, seguridad.
- [Guía de desarrollo](./development_guide.md) — cómo arrancar y trabajar en local / Docker.
- [Modelo de datos](./data-model.md) — entidades base (usuarios, roles, auth).
- [Guía de verificación](./verification-guide.md) — comandos para validar un cambio de punta a punta.
- [Estándares de documentación](./documentation-standards.md) — cómo mantener estos docs.

## 4. Skills del proyecto

- Las skills viven en `.claude/skills/`. Cuando una petición encaje con una skill, carga y sigue su
  `SKILL.md` antes de continuar (y los archivos referenciados que necesite).
- Skills de SDD generadas por OpenSpec: `openspec-propose`, `openspec-explore`, `openspec-apply-change`,
  `openspec-archive-change`. Skills propias: `enrich-us` (Jira), `write-pr-report` (PR con `gh`).
- Agentes de planificación en `.claude/agents/`: `backend-developer`, `product-strategy-analyst`.

## 5. Modelo de planificación (opcional pero recomendado)

Los flujos de planificación (`/opsx:propose`, `enrich-us`, análisis de producto) rinden mejor con un
modelo de razonamiento alto. Si tu setup lo soporta, usa Opus para planificar y un modelo más rápido
para ejecutar tareas mecánicas.

## 6. Actualizar artefactos OpenSpec antes que parchear código

Si aparece un nuevo ajuste/fix **después** de `/opsx:apply` y **antes** de `/opsx:archive`, trátalo
primero como actualización de especificación, no como "arreglo rápido". La documentación (specs) es la
fuente de verdad. Orden:

1. Actualiza los artefactos del cambio afectados (`proposal.md`, delta specs, `tasks.md`). No añadas
   "bugfixes" sueltos: intégralo en la sección de diseño correspondiente.
2. Si hace falta regenerar, usa el paso OpenSpec adecuado antes de codificar.
3. Implementa el código solo cuando los artefactos reflejen la nueva petición.
4. Re-verifica contra los artefactos actualizados antes de archivar.
