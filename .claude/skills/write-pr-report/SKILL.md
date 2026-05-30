---
name: write-pr-report
description: Genera una descripción de Pull Request clara y orientada al revisor a partir de los cambios actuales del repo, y crea el PR con gh. Úsala al cerrar un cambio OpenSpec (antes de /opsx:archive).
---

# Write PR Report

Genera una descripción de PR que un revisor humano entienda rápido y en la que pueda confiar.
Prioriza claridad, señal y revisabilidad sobre exhaustividad.

## Principios

1. Se escribe para un revisor humano, no como documentación.
2. Conciso: elimina lo que no ayude a entender el cambio.
3. No expongas razonamiento interno, artefactos de planificación ni ruido de implementación.
4. Evita verbosidad tipo IA y explicaciones genéricas.

## Reglas de salida (obligatorias)

- **Longitud**: ~150–300 palabras. Sin párrafos largos ni repetición.
- **Incluye**: qué se añadió/cambió, dónde (a alto nivel: slices/capas), por qué importa, cómo se validó (breve).
- **Excluye**: detalles de helpers, ruido de refactor, artefactos de planificación (specs, tasks), mecánica interna salvo que sea crítica.
- **Validación creíble**: "Todos los tests en verde", "Tests de integración añadidos para X". Prohibido: listar comandos crudos, mencionar problemas del entorno local, "según el informe de ejecución".
- **Lenguaje**: español directo. Prefiere "Añade/Corrige/Expone/Mantiene" sobre "La implementación introduce...".
- **No especular ni auditar**: es una descripción, no una review.
- **Nunca menciones**: artefactos internos, "esta sesión", "generado por IA".

## Estructura fija

```markdown
# <Título corto>

## Resumen
<2-3 frases>

## Qué cambió
- agrupado por área (API/router, Services, Repository/DB, Frontend, Tests, Migraciones)

## Validación
### Automática
<bullets cortos: pytest, vitest, lint, build>
### Manual
<bullets cortos o "Ninguna": curl endpoints, E2E Playwright>

## Notas para el revisor
<dónde mirar>

## Riesgos
<solo riesgos reales; p. ej. migración Alembic, cambios de contrato>

## Rollback
<una frase>
```

No añadas secciones extra.

## Proceso

1. Inspecciona los cambios con `git status` y `git diff` (y `git diff <base>...HEAD` si procede).
2. Agrupa por responsabilidad: API/router, Services, Repository/DB, Frontend, Tests, Migraciones.
3. Extrae la intención del cambio.
4. Genera la descripción siguiendo las reglas anteriores.
5. Crea el PR: `gh pr create --title "<título>" --body "<cuerpo>"` (usa HEREDOC para el cuerpo).
   Confirma con el usuario antes de `gh pr create` si la rama aún no se ha empujado.

## Salida

Devuelve la descripción del PR en Markdown y, tras confirmar, crea el PR con `gh`.
