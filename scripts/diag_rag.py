#!/usr/bin/env python3
"""Diagnóstico/evaluación RAG dense-only.

Imprime el top-K que devuelve el retriever de producción (dense_search) para un
conjunto de consultas ES/EN, para verificar que las preguntas en español
recuperan el documento correcto.

uv run python scripts/diag_rag.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.features.butler.rag.retriever import dense_search  # noqa: E402

QUERIES = [
    "¿Qué objetos dropea un caballo?",
    "¿Qué objetos dropea una vaca?",
    "What items does a cow drop?",
    "¿Cómo encanto una espada?",
    "¿Cómo se hace una poción de fuerza?",
]


def _label(doc) -> str:
    name = (
        doc.metadata.get("display_name") or doc.metadata.get("page") or doc.content[:40]
    )
    return f"{doc.doc_type:8} | {name}"


def main() -> None:
    for query in QUERIES:
        print("\n" + "=" * 70)
        print(query)
        for doc in dense_search(query):
            print(f"  {doc.score:.4f}  {_label(doc)}")


if __name__ == "__main__":
    main()
