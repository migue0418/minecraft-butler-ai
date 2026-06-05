## ADDED Requirements

### Requirement: Precalentamiento del RAG en el arranque
El sistema SHALL cargar el modelo de embeddings y el cliente Qdrant una única vez durante el
arranque de la aplicación (lifespan), para evitar latencia por petición en la primera consulta
que usa recuperación. El precalentamiento SHALL forzar la carga del modelo de embeddings y su
primera inferencia (un embed de calentamiento) y SHALL inicializar el cliente Qdrant. El
precalentamiento SHALL ser tolerante a fallos: si el modelo o Qdrant no están disponibles, el
sistema MUST registrar un aviso y continuar el arranque, recurriendo a la carga perezosa en la
primera petición. El precalentamiento SHALL respetar el bypass SSL/carga offline cuando
`SSL_VERIFY=false`.

#### Scenario: Modelo de embeddings y Qdrant cargados en lifespan
- **WHEN** la aplicación arranca con Qdrant disponible y el modelo de embeddings accesible
- **THEN** el modelo de embeddings y el cliente Qdrant quedan inicializados antes de servir peticiones
- **AND** la primera consulta de tipo `question` no paga la carga del modelo (~150 MB) ni la apertura de conexión

#### Scenario: Arranque resiliente si el precalentamiento falla
- **WHEN** Qdrant no está disponible (o el modelo no puede cargarse) durante el arranque
- **THEN** el sistema registra un aviso (`warning`) y completa el arranque sin lanzar error
- **AND** el RAG se carga perezosamente en la primera petición que lo requiera
