## ADDED Requirements

### Requirement: Eliminar rol (admin)
El sistema MUST permitir eliminar roles mediante `DELETE /api/roles/{role_id}` (solo admin), con protección para los roles del sistema (`admin` y `user`). El `role_id` debe ser un entero positivo.

#### Scenario: Eliminación válida
- **WHEN** un admin elimina un rol existente que no es del sistema
- **THEN** responde 204 y el rol queda eliminado

#### Scenario: Rol inexistente
- **WHEN** el `role_id` no corresponde a ningún rol
- **THEN** responde 404 con detalle "Rol no encontrado"

#### Scenario: Intento de eliminar un rol del sistema
- **WHEN** el `role_id` corresponde a `admin` o `user`
- **THEN** responde 400 con detalle "No se puede eliminar un rol del sistema"

#### Scenario: role_id inválido (no positivo)
- **WHEN** el `role_id` es 0 o negativo
- **THEN** responde 422

#### Scenario: Acceso sin rol admin
- **WHEN** un usuario autenticado sin rol `admin` intenta eliminar un rol
- **THEN** responde 403
