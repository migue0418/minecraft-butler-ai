## MODIFIED Requirements

### Requirement: Login con usuario y contraseña
El sistema MUST autenticar mediante `POST /api/auth/login` (`username`, `password`, `remember_me`) y, si
las credenciales son válidas y el usuario está activo y no bloqueado, devolver un `access_token` (tipo `bearer`) y
emitir un refresh token en la cookie HttpOnly. El endpoint está sujeto a rate limiting (10/minuto por IP).

#### Scenario: Credenciales válidas
- **WHEN** un usuario activo no bloqueado envía username y password correctos
- **THEN** responde 200 con `access_token`
- **AND** establece la cookie `refresh_token` (con `max_age` solo si `remember_me` es true)
- **AND** resetea `failed_login_attempts` a 0 y `locked_until` a null

#### Scenario: Credenciales inválidas
- **WHEN** el username no existe o la contraseña es incorrecta
- **THEN** responde 401 con detalle "Credenciales invalidas"
- **AND** si el usuario existe, incrementa `failed_login_attempts`

#### Scenario: Usuario inactivo
- **WHEN** las credenciales son correctas pero el usuario está inactivo
- **THEN** responde 401 con detalle "Usuario inactivo"

#### Scenario: Cuenta bloqueada
- **WHEN** el usuario tiene `locked_until > now` (independientemente de las credenciales)
- **THEN** responde 429 con detalle "Cuenta temporalmente bloqueada. Inténtalo de nuevo más tarde"

#### Scenario: Rate limit superado
- **WHEN** la IP supera 10 peticiones por minuto
- **THEN** responde 429
