# Informe de tests — harden-butler-pipeline

**Fecha:** 2026-06-01
**Rama:** feature/harden-butler-pipeline

## Resultado

```
97 passed, 6 warnings in 22.26s
```

## Tests nuevos añadidos

- `test_ask_rate_limit_returns_429_after_20_requests` — verifica 429 en la petición 21
- `test_ask_voice_transcription_uses_asyncio_to_thread` — verifica que la transcripción usa `to_thread`
- `TestGetLLMCache::test_same_role_returns_same_instance` — verifica que lru_cache funciona
- `TestGetLLMCache::test_different_roles_return_different_instances` — cachés por rol son independientes
- `TestScoreThreshold::test_threshold_filters_low_score_docs` — threshold 0.3 descarta docs < 0.3
- `TestScoreThreshold::test_zero_threshold_returns_all_docs` — default 0.0 no filtra nada
- `TestScoreThreshold::test_high_threshold_returns_empty` — threshold agresivo devuelve lista vacía
- `TestScoreThreshold::test_exact_threshold_boundary_is_inclusive` — score == threshold se incluye

## Cambios de fixture existentes

- `TestGetLlm` en `test_llm_factory.py`: añadidos `setup_method`/`teardown_method` con `cache_clear()` para aislar tests ante la nueva caché de `get_llm`.

## Sin cambios de BD

Este change no muta datos; no se requiere baseline ni restauración.
