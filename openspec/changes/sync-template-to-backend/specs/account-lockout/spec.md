## ADDED Requirements

### Requirement: Bloqueo temporal de cuenta por intentos fallidos
El sistema MUST bloquear temporalmente una cuenta de usuario cuando acumula 5 o más intentos de login fallidos consecutivos. El bloqueo dura 15 minutos desde el último intento fallido que alcanzó el umbral. El contador se reinicia a 0 tras un login exitoso.

#### Scenario: Bloqueo al alcanzar el umbral
- **WHEN** un usuario falla el login 5 veces consecutivas
- **THEN** el sistema establece `locked_until = now + 15 minutos` y responde 429 con detalle "Cuenta temporalmente bloqueada. Inténtalo de nuevo más tarde"

#### Scenario: Intento de login con cuenta bloqueada
- **WHEN** un usuario con `locked_until > now` intenta hacer login (sea con credenciales correctas o incorrectas)
- **THEN** el sistema responde 429 con detalle "Cuenta temporalmente bloqueada. Inténtalo de nuevo más tarde"

#### Scenario: Expiración del bloqueo
- **WHEN** `locked_until <= now` y el usuario envía credenciales correctas
- **THEN** el sistema autentica al usuario, resetea `failed_login_attempts = 0` y `locked_until = null`

#### Scenario: Reset del contador tras login exitoso
- **WHEN** un usuario con intentos fallidos previos (pero no bloqueado) hace login con credenciales correctas
- **THEN** el sistema autentica al usuario y resetea `failed_login_attempts = 0` y `locked_until = null`

#### Scenario: Incremento del contador sin bloqueo
- **WHEN** un usuario falla el login pero el contador resultante es menor que 5
- **THEN** el sistema incrementa `failed_login_attempts` y responde 401 "Credenciales invalidas"
