# Informe de tests — streaming-sentence-chunks

**Fecha:** 2026-06-03
**Rama:** feature/streaming-sentence-chunks

## Resultado

```
119 passed, 6 warnings in 31.32s
```

## Tests nuevos añadidos

**`test_flush_at_boundaries.py` (nuevo — 9 tests):**
- `test_flush_at_sentence_end` — punto seguido de espacio
- `test_flush_at_exclamation` — `!`
- `test_flush_at_question` — `?`
- `test_flush_at_newline` — `\n`
- `test_no_boundary_returns_empty` — sin frontera, buffer completo
- `test_multiple_sentences` — dos frases, rest correcto
- `test_empty_string` — cadena vacía
- `test_decimal_not_split` — `3.14` no se parte
- `test_trailing_newline_flushes` — newline al final vacía el buffer

**`test_service_stream.py` (nuevo — 5 tests):**
- `test_stream_emits_chunks_at_sentence_boundary` — 3 tokens → 2 chunks
- `test_stream_no_boundary_flushes_at_chain_end` — residuo en on_chain_end
- `test_stream_ignores_tokens_from_non_responder_nodes` — classify_intent filtrado
- `test_stream_retry_resets_buffer` — on_chain_start limpia buffer sucio
- `test_stream_move_action_from_chain_end` — move_to_position desde on_chain_end
