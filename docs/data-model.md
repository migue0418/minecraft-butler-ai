# Modelo de datos (base de la plantilla)

Entidades base que trae la plantilla. Amplíalo al añadir nuevos slices con modelos.
Recuerda: todo modelo nuevo se importa en `app.core.database.import_model_modules()` y todo cambio de
schema requiere **migración Alembic** (`alembic/versions/`).

## Entidades

### `User` (`users`) — `app/features/users/models.py`
| Campo | Tipo | Notas |
|---|---|---|
| `id` | int | PK, autoincrement |
| `username` | str(50) | único, indexado |
| `password_hash` | str(255) | hash argon2 (`pwdlib`) |
| `full_name` | str(255)? | nullable |
| `email` | str(255)? | nullable |
| `is_active` | bool | default `True` |
| `failed_login_attempts` | int | default `0`, server_default `'0'` |
| `locked_until` | datetime? | nullable; si > now, cuenta bloqueada temporalmente |
| `created_at` / `updated_at` | datetime | `utcnow`, `onupdate=utcnow` |
| `roles` | M2M → `Role` | vía `user_roles`, `lazy="selectin"` |

### `Role` (`roles`) — `app/features/roles/models.py`
| Campo | Tipo | Notas |
|---|---|---|
| `id` | int | PK, autoincrement |
| `name` | str(50) | único, indexado (p. ej. `admin`) |
| `description` | str(255) | default `""` |
| `created_at` / `updated_at` | datetime | |
| `users` | M2M → `User` | vía `user_roles` |

### `UserRole` (`user_roles`) — tabla de unión
- PK compuesta (`user_id`, `role_id`); FKs con `ondelete="CASCADE"`; `UniqueConstraint(user_id, role_id)`.

### Auth (slice `auth`)
- Almacén de **refresh tokens revocables** por usuario (login/refresh/logout). Al desactivar o eliminar
  un usuario se revocan sus refresh tokens. El acceso usa JWT.

## Reglas de negocio relevantes

- **Último admin protegido**: no se puede eliminar/desactivar/degradar al último admin activo
  (ver `UsersService._ensure_last_admin_is_not_removed`).
- `username` único: crear/actualizar con uno existente devuelve 409.
- **Lockout por intentos fallidos**: tras 5 fallos consecutivos, `locked_until = now + 15 min`. Se resetea en login exitoso. Consultar `AuthService._MAX_FAILED_ATTEMPTS` y `_LOCKOUT_MINUTES`.
- **Roles de sistema** (`admin`, `user`): no se pueden eliminar ni renombrar.

## Invariantes al evolucionar el modelo

1. Define el modelo en `<feature>/models.py` heredando de `Base`.
2. Impórtalo en `app.core.database.import_model_modules()`.
3. Genera la migración Alembic y revísala antes de aplicarla.
4. Actualiza este documento.
