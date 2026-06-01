## ADDED Requirements

### Requirement: Aceptar world_context en POST /api/butler/ask
El sistema SHALL aceptar un campo `world_context` opcional en el body JSON de `POST /api/butler/ask`. Si el campo está ausente o es null, el comportamiento SHALL ser idéntico al actual (retrocompatible).

#### Scenario: Petición sin world_context funciona igual que antes
- **WHEN** un cliente envía `{"message": "¿Cómo crafteo una espada?"}` sin campo `world_context`
- **THEN** el servidor responde 200 con acciones del butler, igual que antes de este cambio

#### Scenario: Petición con world_context válido es aceptada
- **WHEN** un cliente envía un body JSON con `message` y un `world_context` con estructura válida (player, chests, nearby)
- **THEN** el servidor responde 200 y el butler usa el contexto si la pregunta lo requiere

#### Scenario: world_context malformado devuelve 422
- **WHEN** se envía un `world_context` con estructura incorrecta (ej. campo requerido ausente)
- **THEN** el servidor responde 422 con detalle de validación

### Requirement: Selección selectiva de contexto por el clasificador
El sistema SHALL determinar en el nodo `classify_intent` si la pregunta del usuario requiere contexto del mundo, usando un campo `needs_world_context: bool` en el structured output del LLM. El contexto SHALL inyectarse en el prompt solo cuando `needs_world_context=True` y `world_context` no sea null.

#### Scenario: Pregunta de crafteo no recibe contexto
- **WHEN** el usuario pregunta "¿Cómo crafteo una espada de diamante?" con world_context presente
- **THEN** el clasificador devuelve `needs_world_context=False` y el contexto NO se inyecta en el prompt del LLM

#### Scenario: Pregunta de inventario sí recibe contexto
- **WHEN** el usuario pregunta "¿Tengo materiales para una armadura de hierro?" con world_context presente
- **THEN** el clasificador devuelve `needs_world_context=True` y el contexto se inyecta en el prompt del LLM

#### Scenario: Pregunta sin world_context no falla aunque necesite contexto
- **WHEN** el usuario pregunta "¿Qué hay en mis cofres?" pero no se envió world_context
- **THEN** el servidor responde 200; Alfred indica que no tiene acceso al contexto del mundo en ese momento

### Requirement: Formato compacto del contexto para el LLM
El sistema SHALL formatear el `world_context` como texto legible compacto antes de inyectarlo en el prompt, usando los IDs de Minecraft tal cual (ej. `minecraft:iron_ingot`). El formato SHALL limitar el inventario a los 10 ítems con mayor cantidad, los cofres a 5 ítems por cofre y los animales a 5 tipos, para acotar el uso de tokens.

#### Scenario: Formato generado es legible y compacto
- **WHEN** el world_context incluye inventario con 20 tipos de ítems y 2 cofres registrados
- **THEN** el texto formateado contiene la posición del jugador, los top-10 ítems del inventario con su cantidad, el contenido resumido de cada cofre, y los animales/cultivos cercanos; el total no supera 200 tokens

#### Scenario: Contexto inyectado en system prompt, no en historial
- **WHEN** se procesa una petición con world_context
- **THEN** el contexto aparece en el system prompt del LLM para esa llamada pero NO se añade al historial `messages` persistido en Redis
