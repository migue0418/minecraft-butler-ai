# Health Specification

## Purpose

Endpoint público de comprobación de vida (liveness probe) para orquestadores, balanceadores y
monitores. No requiere autenticación.

## Requirements

### Requirement: Health check
El sistema MUST exponer `GET /health` sin autenticación y devolver `{ "status": "ok" }` con código 200
mientras la aplicación esté en marcha.

#### Scenario: Aplicación en marcha
- **WHEN** se llama a `GET /health` (con o sin token)
- **THEN** responde 200 con el cuerpo `{"status": "ok"}`
