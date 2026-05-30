# Roles Specification

## Purpose

Gestión del catálogo de roles del sistema bajo el prefijo `/api/roles`. Todos los endpoints están
restringidos al rol `admin`. Los roles `admin` y `user` son **roles del sistema** y no pueden
renombrarse.

## Requirements

### Requirement: Listar roles (admin)
El sistema MUST exponer `GET /api/roles` (solo admin) y devolver el listado de roles con
`id`, `name` y `description`.

#### Scenario: Acceso autorizado
- **WHEN** un admin autenticado llama a `GET /api/roles`
- **THEN** responde 200 con la lista de roles

#### Scenario: Acceso sin rol admin
- **WHEN** un usuario autenticado sin rol `admin` llama al endpoint
- **THEN** responde 403

### Requirement: Detalle de rol (admin)
El sistema MUST exponer `GET /api/roles/{role_id}` (solo admin).

#### Scenario: Rol existente
- **WHEN** un admin solicita un rol existente
- **THEN** responde 200 con `id`, `name` y `description`

#### Scenario: Rol inexistente
- **WHEN** el `role_id` no existe
- **THEN** responde 404 con detalle "Rol no encontrado"

### Requirement: Crear rol (admin)
El sistema MUST permitir crear roles mediante `POST /api/roles` (solo admin), con `name`
de 1 a 50 caracteres y `description` opcional de hasta 255 caracteres.

#### Scenario: Creación válida
- **WHEN** un admin envía un `name` único y una `description` opcional
- **THEN** responde 201 con el rol creado

#### Scenario: Nombre duplicado
- **WHEN** ya existe un rol con ese `name`
- **THEN** responde 409 con detalle "Ya existe un rol con ese nombre"

#### Scenario: Payload inválido
- **WHEN** `name` está vacío o excede 50 caracteres, o `description` excede 255
- **THEN** responde 422

### Requirement: Actualizar rol (admin)
El sistema MUST permitir actualizar `name` y `description` mediante `PUT /api/roles/{role_id}` (solo
admin), validando unicidad de `name` y protegiendo los roles del sistema.

#### Scenario: Actualización válida
- **WHEN** un admin actualiza un rol no del sistema con datos válidos
- **THEN** responde 200 con el rol actualizado

#### Scenario: Rol inexistente
- **WHEN** el `role_id` no existe
- **THEN** responde 404

#### Scenario: Nombre duplicado al actualizar
- **WHEN** el nuevo `name` ya pertenece a otro rol distinto
- **THEN** responde 409 con detalle "Ya existe un rol con ese nombre"

#### Scenario: Renombrar un rol del sistema
- **WHEN** se intenta cambiar el `name` de un rol del sistema (`admin` o `user`)
- **THEN** responde 400 con detalle "No se puede renombrar un rol del sistema"

#### Scenario: Actualizar la descripción de un rol del sistema sin renombrar
- **WHEN** se actualiza un rol del sistema manteniendo su `name`
- **THEN** la operación se acepta y responde 200
