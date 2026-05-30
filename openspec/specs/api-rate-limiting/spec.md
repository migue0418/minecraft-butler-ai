# API Rate Limiting Specification

## Purpose

Protección contra ataques de fuerza bruta y abuso de los endpoints de autenticación mediante rate limiting por IP usando SlowAPI.

## Requirements

### Requirement: Rate limiting en endpoints de autenticación
El sistema MUST limitar la tasa de peticiones en los endpoints de autenticación para proteger contra ataques de fuerza bruta. Se usa SlowAPI con `key_func=get_remote_address`. Los límites son: 10 peticiones/minuto para `POST /api/auth/login` y `POST /api/auth/token`; 20 peticiones/minuto para `POST /api/auth/refresh`. Cuando se supera el límite, el sistema responde 429.

#### Scenario: Límite superado en login
- **WHEN** una IP envía más de 10 peticiones a `POST /api/auth/login` en un minuto
- **THEN** la petición número 11 o superior responde 429 Too Many Requests

#### Scenario: Límite superado en token
- **WHEN** una IP envía más de 10 peticiones a `POST /api/auth/token` en un minuto
- **THEN** la petición número 11 o superior responde 429

#### Scenario: Límite superado en refresh
- **WHEN** una IP envía más de 20 peticiones a `POST /api/auth/refresh` en un minuto
- **THEN** la petición número 21 o superior responde 429

#### Scenario: Petición dentro del límite
- **WHEN** una IP no ha superado el límite en la ventana de tiempo
- **THEN** el endpoint procesa la petición normalmente
