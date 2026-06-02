## MODIFIED Requirements

### Requirement: Aceptar world_context en POST /api/butler/ask
El sistema SHALL aceptar un campo `world_context` opcional en el body JSON de `POST /api/butler/ask`. El objeto `world_context.nearby` SHALL aceptar un campo `monsters` opcional (lista de `{type: str, count: int}`) con default `[]`. Los cofres con `items: []` SHALL ser validados y procesados correctamente (no son un error). Si el campo `monsters` está ausente, el comportamiento SHALL ser idéntico al anterior (retrocompatible).

#### Scenario: Petición sin world_context funciona igual que antes
- **WHEN** un cliente envía `{"message": "¿Cómo crafteo una espada?"}` sin campo `world_context`
- **THEN** el servidor responde 200 con acciones del butler, igual que antes de este cambio

#### Scenario: Petición con world_context válido incluyendo monsters es aceptada
- **WHEN** un cliente envía `world_context` con `nearby.monsters: [{"type":"minecraft:zombie","count":1}]`
- **THEN** el servidor responde 200 y el butler procesa el contexto incluyendo los monstruos

#### Scenario: world_context sin monsters es retrocompatible
- **WHEN** se envía `world_context` con `nearby` que no incluye el campo `monsters`
- **THEN** el servidor responde 200 y trata `monsters` como lista vacía

#### Scenario: Cofre vacío en world_context es válido
- **WHEN** se envía `world_context` con un cofre que tiene `"items": []`
- **THEN** el servidor acepta el request sin error de validación (422)

### Requirement: Formato compacto del contexto para el LLM
El sistema SHALL formatear el `world_context` como texto legible compacto antes de inyectarlo en el prompt. El formato SHALL incluir los monstruos hostiles cercanos con prioridad sobre los animales (aparecen antes en el texto). Los cofres vacíos SHALL mostrarse explícitamente como `"vacío"` en lugar de omitirse, para informar al LLM de su existencia.

#### Scenario: Monstruos aparecen en el texto formateado
- **WHEN** el world_context incluye `nearby.monsters: [{"type":"minecraft:zombie","count":2}]`
- **THEN** el texto formateado contiene una línea de monstruos cercanos con `minecraft:zombie`

#### Scenario: Monstruos aparecen antes que animales en el texto
- **WHEN** el world_context incluye tanto `monsters` como `animals`
- **THEN** la línea de monstruos precede a la línea de animales en el texto formateado

#### Scenario: Cofre vacío aparece en el texto como vacío
- **WHEN** el world_context incluye un cofre con `"items": []`
- **THEN** el texto formateado muestra el nombre del cofre seguido de `"vacío"`

#### Scenario: Formato generado es legible y compacto
- **WHEN** el world_context incluye inventario con 20 tipos de ítems y 2 cofres registrados
- **THEN** el texto formateado contiene la posición del jugador, los top-10 ítems del inventario con su cantidad, el contenido resumido de cada cofre, y los animales/cultivos cercanos; el total no supera 200 tokens
