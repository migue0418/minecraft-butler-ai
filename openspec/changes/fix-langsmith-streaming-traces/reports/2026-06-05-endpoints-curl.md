# Informe de pruebas de endpoints (curl) — fix-langsmith-streaming-traces

Fecha: 2026-06-05
Instancia de prueba: `uvicorn app.main:app --port 8011` (rama `feature/fix-langsmith-streaming-traces`).
Servicios: PostgreSQL (5432), Redis (6379), Qdrant (6333) disponibles.

## 1. `POST /api/butler/ask-stream` (happy path)

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8011/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"***","remember_me":false}' | jq -r .access_token)

curl -s -N -D - -X POST http://127.0.0.1:8011/api/butler/ask-stream \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"message":"Hola, quien eres?"}'
```

Respuesta:
```
HTTP/1.1 200 OK
content-type: text/event-stream; charset=utf-8
transfer-encoding: chunked

data: {"type": "echo", "message": "[Tú] Hola, quien eres?"}
data: {"type": "speak", "message": "Soy Alfred, tu asistente de Minecraft."}
data: {"type": "speak", "message": "Pregunta lo que necesites."}
data: [DONE]
```

✅ `200`, `text/event-stream`, echo inicial, **troceado por frases** (dos eventos `speak`),
`[DONE]` final. Contrato SSE preservado tras el refactor productor/consumidor.

## 2. Casos de error

| Caso | Comando | Esperado | Obtenido |
|------|---------|----------|----------|
| Sin token | `POST /ask-stream` sin `Authorization` | 401 | **401** ✅ |
| Payload inválido | `POST /ask-stream` con `{}` (sin `message`) | 422 | **422** ✅ |
| Voz audio vacío | `POST /ask-voice-stream` con WAV de silencio | 422 | **422** ✅ |

El `422` de voz proviene de la transcripción vacía (`No se pudo transcribir el audio.`),
ejercitando la ruta multipart + STT + manejo de error del endpoint.

## 3. `POST /api/butler/ask-voice-stream` (SSE)
El stream SSE de voz reutiliza `ButlerService.stream()`, idéntico al de texto (verificado en
§1). La generación de audio con voz real no es reproducible en este entorno, por lo que se
verifica: (a) la ruta multipart/STT y su manejo de error (§2), y (b) la equivalencia del
camino de streaming vía tests unitarios y §1.

## 4. Restauración de BD
Ninguna operación mutó datos (login es de solo lectura sobre usuarios; el butler no escribe
en la BD relacional). No se requiere restauración.

## 5. Verificación de tracing en LangSmith (CONFIRMADA vía API)
Se arrancó una instancia con el fix y tracing activo (`LANGCHAIN_TRACING_V2=true`, endpoint EU,
proyecto `MinecraftButlerAI`) y se lanzó `/api/butler/ask-stream` con un marcador único. Se
consultó la **API de LangSmith** (no la UI) para inspeccionar el árbol del run:

```
ROOT: butler-text-stream
TOTAL runs en el trace: 9  | HIJOS: 8
   - chain   classify_intent
   - chain   RunnableSequence
   - llm     ChatAnthropic
   - parser  PydanticToolsParser
   - chain   route_intent
   - chain   retrieve_context
   - chain   answer_question
   - llm     ChatAnthropic
```

✅ **El árbol de nodos aparece anidado** bajo `butler-text-stream` (8 hijos), no plano. El fix
restaura la traza completa en el camino de streaming. A/B frente al código previo (main), cuyas
trazas de streaming quedaban planas (input→output).
