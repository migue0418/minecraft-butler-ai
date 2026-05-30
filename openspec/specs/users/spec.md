# Users Specification

## Purpose

Gestión de cuentas de usuario y sus roles, bajo el prefijo `/api/users`. La administración (listar,
ver, crear, actualizar, borrar, restablecer contraseña) está restringida al rol `admin`; cualquier
usuario autenticado puede cambiar su propia contraseña.

## Requirements

### Requirement: Listar usuarios (admin)
El sistema MUST exponer `GET /api/users` accesible solo para usuarios con rol `admin` y devolver el
listado de usuarios ordenado por `username` ascendente, con `id`, `username`, `full_name`, `email`,
`is_active` y la lista de nombres de roles.

#### Scenario: Acceso autorizado
- **WHEN** un admin autenticado llama a `GET /api/users`
- **THEN** responde 200 con la lista de usuarios ordenada por username asc

#### Scenario: Acceso sin rol admin
- **WHEN** un usuario autenticado sin rol `admin` llama al endpoint
- **THEN** responde 403

### Requirement: Detalle de usuario (admin)
El sistema MUST exponer `GET /api/users/{user_id}` (solo admin) que devuelve el detalle del usuario
incluyendo `role_ids` además de los nombres de roles.

#### Scenario: Usuario existente
- **WHEN** un admin solicita un usuario existente
- **THEN** responde 200 con el detalle incluyendo `role_ids`

#### Scenario: Usuario inexistente
- **WHEN** el `user_id` no existe
- **THEN** responde 404 con detalle "Usuario no encontrado"

### Requirement: Crear usuario (admin)
El sistema MUST permitir crear usuarios mediante `POST /api/users` (solo admin) hasheando la
contraseña con argon2 y asignando al menos un rol válido.

#### Scenario: Creación válida
- **WHEN** un admin envía un payload válido con al menos un `role_id` existente
- **THEN** responde 201 con el detalle del usuario creado

#### Scenario: Username duplicado
- **WHEN** ya existe un usuario con ese `username`
- **THEN** responde 409 con detalle "Ya existe un usuario con ese username"

#### Scenario: role_ids inválidos
- **WHEN** alguno de los `role_ids` no corresponde a un rol existente
- **THEN** responde 400 con detalle "Uno o varios roles no existen"

#### Scenario: Payload inválido
- **WHEN** falta `username`/`password` o `role_ids` está vacío
- **THEN** responde 422

### Requirement: Actualizar usuario (admin)
El sistema MUST permitir actualizar `username`, `full_name`, `email`, `is_active` y `role_ids` de un
usuario mediante `PUT /api/users/{user_id}` (solo admin), validando duplicados de username y la
existencia de los roles.

#### Scenario: Actualización válida
- **WHEN** un admin actualiza un usuario existente con datos válidos
- **THEN** responde 200 con el detalle actualizado

#### Scenario: Username duplicado al actualizar
- **WHEN** el nuevo `username` ya pertenece a otro usuario
- **THEN** responde 409

#### Scenario: Desactivar usuario
- **WHEN** la actualización pone `is_active=false`
- **THEN** además de aplicarse, se revocan todos los refresh tokens de ese usuario

### Requirement: Eliminar usuario (admin)
El sistema MUST permitir eliminar usuarios mediante `DELETE /api/users/{user_id}` (solo admin),
revocando sus refresh tokens.

#### Scenario: Eliminación válida
- **WHEN** un admin elimina un usuario existente
- **THEN** responde 204 y se revocan sus refresh tokens

#### Scenario: Usuario inexistente
- **WHEN** el `user_id` no existe
- **THEN** responde 404

### Requirement: Protección del último admin activo
El sistema MUST impedir que una operación deje al sistema sin ningún admin activo: no se puede
eliminar, desactivar ni quitar el rol `admin` al último administrador activo.

#### Scenario: Borrado del último admin activo
- **WHEN** se intenta borrar al único admin activo
- **THEN** responde 400 con detalle "No se puede eliminar o degradar al ultimo admin activo"

#### Scenario: Degradación del último admin activo
- **WHEN** una actualización quitaría el rol `admin` o desactivaría al único admin activo
- **THEN** responde 400 con el mismo detalle, sin aplicar el cambio

### Requirement: Cambiar la propia contraseña
El sistema MUST permitir a cualquier usuario autenticado cambiar su contraseña mediante
`POST /api/users/me/change-password`, verificando la contraseña actual y revocando sus refresh tokens.

#### Scenario: Cambio válido
- **WHEN** un usuario autenticado envía `current_password` correcta y una nueva
- **THEN** responde 204, actualiza el hash y revoca todos sus refresh tokens

#### Scenario: Contraseña actual incorrecta
- **WHEN** `current_password` no coincide con la del usuario
- **THEN** responde 401 con detalle "La contrasena actual no es valida"

### Requirement: Restablecer contraseña (admin)
El sistema MUST permitir a un admin restablecer la contraseña de cualquier usuario mediante
`POST /api/users/{user_id}/reset-password`, revocando los refresh tokens del usuario afectado.

#### Scenario: Reset válido
- **WHEN** un admin envía una `new_password` para un usuario existente
- **THEN** responde 204, actualiza el hash y revoca los refresh tokens de ese usuario

#### Scenario: Usuario inexistente
- **WHEN** el `user_id` no existe
- **THEN** responde 404
