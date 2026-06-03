## 0. Setup (OBLIGATORIO - PRIMER PASO)

- [x] 0.1 Leer el plan técnico en `.claude/doc/world-context-monsters/backend.md` antes de tocar código
- [x] 0.2 Crear rama `feature/world-context-monsters` desde main

## 1. Schemas (TDD)

- [x] 1.1 En `app/features/butler/schemas.py`: añadir `MonsterGroup(type: str, count: int)` y añadir `monsters: list[MonsterGroup] = []` a `NearbyContext`
- [x] 1.2 Ampliar `tests/features/butler/test_schemas.py`: caso con `nearby.monsters` válido, caso sin `monsters` (retrocompatible), caso con cofre `items: []`

## 2. `format_world_context` (TDD)

- [x] 2.1 En `app/features/butler/graph/nodes.py::format_world_context`: añadir sección monstruos (antes que animales), y mostrar cofres vacíos como `"vacío"` en lugar de omitirlos
- [x] 2.2 En `tests/features/butler/test_nodes.py`: tests de monstruos en texto, orden monstruos > animales, y cofre vacío aparece como `"vacío"`

## 3. Tests y estado de BD (OBLIGATORIO)

- [x] 3.1 `uv run pytest -q` en verde (105/105); informe en `reports/2026-06-03-backend-tests.md`; informe en `openspec/changes/world-context-monsters/reports/YYYY-MM-DD-backend-tests.md`

## 4. Pruebas manuales con curl (OBLIGATORIO - EL AGENTE LO EJECUTA)

- [x] 4.1 `POST /api/butler/ask` con JSON completo → 200; Alfred detectó zombie y araña ✓
- [x] 4.2 `POST /api/butler/ask` sin `monsters` → 200 (retrocompatible) ✓
- [x] 4.3 Informe en `reports/2026-06-03-curl.md`

## 5. Cierre (OBLIGATORIO)

- [x] 5.1 Actualizar `docs/backend-standards.md`: documentar `MonsterGroup` y cambio en `NearbyContext`
- [x] 5.2 PR con `gh pr create` usando la skill `write-pr-report`
