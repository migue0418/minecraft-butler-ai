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
contraseña con argon2 y asignando al menos un rol válido. Las validaciones son: `username` entre 3 y 50 caracteres, solo alfanuméricos, guion y guion bajo (`^[a-zA-Z0-9_-]+$`); `password` entre 8 y 128 caracteres; `email` válido (formato EmailStr) si se proporciona; `role_ids` debe tener al menos 1 elemento.

#### Scenario: Creación válida
- **WHEN** un admin envía un payload válido con al menos un `role_id` existente
- **THEN** responde 201 con el detalle del usuario creado

#### Scenario: Username duplicado
- **WHEN** ya existe un usuario con ese `username`
- **THEN** responde 409 con detalle "Ya existe un usuario con ese username"

#### Scenario: role_ids inválidos
- **WHEN** alguno de los `role_ids` no corresponde a un rol existente
- **THEN** responde 400 con detalle "Uno o varios roles no existen"

#### Scenario: Payload inválido — username demasiado corto o caracteres inválidos
- **WHEN** `username` tiene menos de 3 caracteres o contiene caracteres no permitidos
- **THEN** responde 422

#### Scenario: Payload inválido — password demasiado corta
- **WHEN** `password` tiene menos de 8 caracteres
- **THEN** responde 422

#### Scenario: Email inválido
- **WHEN** se proporciona un `email` con formato inválido
- **THEN** responde 422

### Requirement: Actualizar usuario (admin)
El sistema MUST permitir actualizar `username`, `full_name`, `email`, `is_active` y `role_ids` de un
usuario mediante `PUT /api/users/{user_id}` (solo admin), validando duplicados de username y la
existencia de los roles. Las mismas reglas de validación que en creación aplican. `role_ids` debe tener al menos 1 elemento.

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
`POST /api/users/me/change-password`, verificando la contraseña actual y revocando sus refresh tokens. La nueva contraseña debe tener entre 8 y 128 caracteres.

#### Scenario: Cambio válido
- **WHEN** un usuario autenticado envía `current_password` correcta y una nueva (≥ 8 caracteres)
- **THEN** responde 204, actualiza el hash y revoca todos sus refresh tokens

#### Scenario: Contraseña actual incorrecta
- **WHEN** `current_password` no coincide con la del usuario
- **THEN** responde 401 con detalle "La contraseña actual no es válida"

#### Scenario: Nueva contraseña demasiado corta
- **WHEN** `new_password` tiene menos de 8 caracteres
- **THEN** responde 422

### Requirement: Restablecer contraseña (admin)
El sistema MUST permitir a un admin restablecer la contraseña de cualquier usuario mediante
`POST /api/users/{user_id}/reset-password`, revocando los refresh tokens del usuario afectado. La nueva contraseña debe tener entre 8 y 128 caracteres.

#### Scenario: Reset válido
- **WHEN** un admin envía una `new_password` (≥ 8 caracteres) para un usuario existente
- **THEN** responde 204, actualiza el hash y revoca los refresh tokens de ese usuario

#### Scenario: Usuario inexistente
- **WHEN** el `user_id` no existe
- **THEN** responde 404

#### Scenario: Contraseña demasiado corta en reset
- **WHEN** `new_password` tiene menos de 8 caracteres
- **THEN** responde 422

### Requirement: Estado de bloqueo en respuestas de usuario
El sistema MUST incluir los campos `is_locked` (bool) y `locked_until` (datetime | null) en todas las
respuestas `UserResponse` y `UserDetailResponse`, indicando si la cuenta está temporalmente bloqueada.

#### Scenario: Usuario sin bloqueo
- **WHEN** se obtiene o lista un usuario cuyo `locked_until` es null o está en el pasado
- **THEN** `is_locked` es `false` y `locked_until` es null

#### Scenario: Usuario bloqueado actualmente
- **WHEN** se obtiene o lista un usuario cuyo `locked_until > now`
- **THEN** `is_locked` es `true` y `locked_until` refleja el momento de desbloqueo
