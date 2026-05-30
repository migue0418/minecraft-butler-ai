# Estándares de documentación

Cómo mantener la documentación técnica de la plantilla. Estos `docs/` son la referencia versionada que
viaja con el template y que alimenta el contexto de OpenSpec y a los agentes.

## Estructura

- `docs/base-standards.md` — principios y puntero al resto.
- `docs/backend-standards.md`, `docs/frontend-standards.md` — estándares por área.
- `docs/development_guide.md` — arrancar/trabajar + flujo SDD.
- `docs/data-model.md` — entidades base.
- `docs/verification-guide.md` — cómo validar un cambio.
- `docs/documentation-standards.md` — este documento.

(`docs/superpowers/` queda fuera de control de versiones; es material local.)

## Cuándo actualizar (obligatorio)

Actualiza la doc afectada **dentro del mismo cambio** cuando:
- Cambie un contrato de API (endpoints, request/response).
- Cambie el modelo de datos (nueva entidad/campo/relación) → actualiza `data-model.md`.
- Cambie la arquitectura o una convención → actualiza `*-standards.md`.
- Cambien comandos o el flujo de trabajo → actualiza `development_guide.md` / `verification-guide.md`.

Es uno de los pasos `(OBLIGATORIO)` del cierre de un cambio OpenSpec.

## Estilo

- Español, claro y conciso. Prioriza ejemplos reales del codebase sobre teoría.
- No dupliques: si algo vive en un estándar, enlázalo en vez de copiarlo.
- Mantén `CLAUDE.md` (resumen rápido local) coherente con estos `docs/`; ante conflicto, manda el código real.
- Evita documentar lo obvio; documenta el *porqué* y las invariantes no evidentes.

## Relación con OpenSpec

- Las **specs** (`openspec/specs/`) describen el comportamiento del sistema (fuente de verdad del *qué*).
- Estos `docs/` describen **cómo** construimos (stack, patrones, convenciones).
- Tras `/opsx:archive`, los delta specs se fusionan en `openspec/specs/`; si el cambio alteró
  convenciones o arquitectura, refleja también el *cómo* aquí.
