#!/usr/bin/env python3
"""Script de ingesta de datos Minecraft en Qdrant.

Fuentes:
  - PrismarineJS/minecraft-data 1.21 (ítems, recetas, entidades)
  - Minecraft Wiki MediaWiki API (mecánicas)

Uso:
  uv run python scripts/ingest.py [--force]

  --force: reindexa aunque la colección ya tenga datos.

Idempotente: si la colección existe y tiene puntos, no reindexa
(a menos que se pase --force).
"""

from __future__ import annotations

import argparse
import os
import ssl
import sys
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Añadir raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Bypass SSL para entornos con proxy corporativo
# (necesario para descargar modelos de HuggingFace Hub y datos de GitHub/Wiki)
os.environ.setdefault("CURL_CA_BUNDLE", "")
os.environ.setdefault("REQUESTS_CA_BUNDLE", "")
ssl._create_default_https_context = ssl._create_unverified_context  # noqa: SLF001
warnings.filterwarnings("ignore", message=".*Unverified HTTPS.*")
warnings.filterwarnings("ignore", message=".*InsecureRequestWarning.*")

# Configurar huggingface_hub para no verificar SSL (usa httpx internamente)
import httpx  # noqa: E402
from huggingface_hub.utils._http import set_client_factory  # noqa: E402


def _no_ssl_factory() -> httpx.Client:
    return httpx.Client(verify=False)


set_client_factory(_no_ssl_factory)

# ── Constantes de fuentes de datos ──────────────────────────────────────────

PRISMARINE_BASE = (
    "https://raw.githubusercontent.com/PrismarineJS/minecraft-data"
    "/master/data/pc/1.21.6"
)
ITEMS_URL = f"{PRISMARINE_BASE}/items.json"
RECIPES_URL = f"{PRISMARINE_BASE}/recipes.json"
ENTITIES_URL = f"{PRISMARINE_BASE}/entities.json"

WIKI_API = "https://minecraft.wiki/api.php"
WIKI_MECHANIC_PAGES = [
    "Combat",
    "Crafting",
    "Enchanting",
    "Experience",
    "Farming",
    "Mining",
    "Redstone_circuit",
    "Spawning",
    "Trading",
    "Brewing",
]
WIKI_RATE_LIMIT_SECONDS = 0.5

# Dimensiones del modelo paraphrase-multilingual-MiniLM-L12-v2
DENSE_DIM = 384

BATCH_SIZE = 100


# ── Modelo de documento interno ──────────────────────────────────────────────


@dataclass
class IngestDocument:
    doc_id: str
    content: str
    doc_type: str
    metadata: dict = field(default_factory=dict)
    parent_content: str = ""


# ── Wiki batch fetcher ────────────────────────────────────────────────────────

WIKI_BATCH_SIZE = (
    10  # MediaWiki API trunca extractos con batches >10 para páginas con templates
)


def _fetch_wiki_extracts_batch(titles: list[str]) -> dict[str, str]:
    """Descarga extractos de texto plano de la Minecraft Wiki en batches de 10.

    Usa redirects=true para cubrir variantes (Oak Planks → Planks,
    Deepslate Coal Ore → Coal Ore, etc.) almacenando el contenido bajo el
    título ORIGINAL para que el lookup funcione correctamente.

    Returns:
        Dict {título_original: extracto}.
    """
    import re

    import httpx

    extracts: dict[str, str] = {}

    for i in range(0, len(titles), WIKI_BATCH_SIZE):
        batch = titles[i : i + WIKI_BATCH_SIZE]
        titles_param = "|".join(batch)
        try:
            response = httpx.get(
                WIKI_API,
                params={
                    "action": "query",
                    "prop": "extracts",
                    "exintro": "true",
                    "explaintext": "true",
                    "redirects": "true",
                    "titles": titles_param,
                    "format": "json",
                    "formatversion": "2",
                },
                timeout=30.0,
                verify=False,
            )
            response.raise_for_status()
            data = response.json()
            query = data.get("query", {})

            # título_final → extracto
            page_extracts: dict[str, str] = {}
            for page in query.get("pages", []):
                if page.get("missing"):
                    continue
                ptitle = page.get("title", "")
                extract = page.get("extract", "").strip()
                if extract:
                    extract = re.sub(r"\n{2,}", " ", extract)
                    extract = re.sub(r"\s{2,}", " ", extract)
                    page_extracts[ptitle] = extract[:600]

            # Mapa inverso: título_original → título_final
            # (normalizations + redirect chains)
            reverse: dict[str, str] = {}
            for norm in query.get("normalized", []) or []:
                reverse[norm.get("from", "")] = norm.get("to", "")
            for redir in query.get("redirects", []) or []:
                src = redir.get("from", "")
                dst = redir.get("to", "")
                # Resolver cadenas: si dst también tiene mapping, seguirlo
                final = reverse.get(dst, dst)
                reverse[src] = final

            for title in batch:
                final = reverse.get(title, title)
                extract = page_extracts.get(final) or page_extracts.get(title, "")
                if extract:
                    extracts[title] = extract

        except Exception as e:
            print(
                f"[WARN] Wiki batch fetch failed for batch {i // WIKI_BATCH_SIZE + 1}: {e}",
            )

        time.sleep(WIKI_RATE_LIMIT_SECONDS)

    return extracts


# ── Funciones de construcción de documentos ──────────────────────────────────


def build_item_documents() -> list[IngestDocument]:
    import httpx

    print("[INFO] Descargando ítems de PrismarineJS/minecraft-data...")
    items_data: list[dict] = (
        httpx.get(ITEMS_URL, timeout=30.0, verify=False).raise_for_status().json()
    )

    # Obtener extractos de la wiki para todos los ítems (batches de 50)
    display_names = [
        item.get("displayName", item.get("name", "")) for item in items_data
    ]
    print(
        f"[INFO] Descargando extractos wiki para {len(display_names)} ítems ({len(display_names) // WIKI_BATCH_SIZE + 1} batches)...",
    )
    wiki_extracts = _fetch_wiki_extracts_batch(display_names)
    print(f"[INFO] Extractos wiki obtenidos: {len(wiki_extracts)}/{len(display_names)}")

    docs: list[IngestDocument] = []
    for item in items_data:
        item_name: str = item.get("name", "")
        display_name: str = item.get("displayName", item_name)
        stack_size: int = item.get("stackSize", 64)

        wiki_text = wiki_extracts.get(display_name, "")
        if wiki_text:
            # Documento rico: extracto wiki como contenido principal
            content = f"{display_name}: {wiki_text}"
        else:
            # Fallback mínimo (sin boilerplate genérico)
            content = f"{display_name} ({item_name}): Minecraft item. Stack size: {stack_size}."

        docs.append(
            IngestDocument(
                doc_id=f"item_{item_name}",
                content=content,
                doc_type="item",
                metadata={
                    "doc_type": "item",
                    "item_id": item_name,
                    "display_name": display_name,
                    "stack_size": stack_size,
                    "has_wiki": bool(wiki_text),
                },
            ),
        )
    return docs


def build_mob_documents() -> list[IngestDocument]:
    import httpx

    print("[INFO] Descargando entidades de PrismarineJS/minecraft-data...")
    entities_data: list[dict] = (
        httpx.get(ENTITIES_URL, timeout=30.0, verify=False).raise_for_status().json()
    )

    # Obtener extractos de la wiki para todos los mobs (~70 entidades = 2 batches)
    display_names = [
        entity.get("displayName", entity.get("name", "")) for entity in entities_data
    ]
    print(
        f"[INFO] Descargando extractos wiki para {len(display_names)} entidades ({len(display_names) // WIKI_BATCH_SIZE + 1} batches)...",
    )
    wiki_extracts = _fetch_wiki_extracts_batch(display_names)
    print(f"[INFO] Extractos wiki obtenidos: {len(wiki_extracts)}/{len(display_names)}")

    docs: list[IngestDocument] = []
    for entity in entities_data:
        name: str = entity.get("name", "")
        display_name: str = entity.get("displayName", name)
        entity_type: str = entity.get("type", "unknown")
        category: str = entity.get("category", "")

        wiki_text = wiki_extracts.get(display_name, "")
        if wiki_text:
            # Documento rico: extracto wiki como contenido principal
            content = f"{display_name}: {wiki_text}"
        else:
            # Fallback con tipo y categoría (sin dimensiones inútiles)
            content = (
                f"{display_name} ({name}): Minecraft {entity_type} mob. "
                f"Category: {category}."
            )

        docs.append(
            IngestDocument(
                doc_id=f"mob_{name}",
                content=content,
                doc_type="mob",
                metadata={
                    "doc_type": "mob",
                    "mob_id": name,
                    "display_name": display_name,
                    "mob_type": entity_type,
                    "has_wiki": bool(wiki_text),
                },
            ),
        )
    return docs


def build_mechanic_documents() -> list[IngestDocument]:
    import httpx

    docs: list[IngestDocument] = []
    print(
        f"[INFO] Descargando {len(WIKI_MECHANIC_PAGES)} páginas de la Minecraft Wiki...",
    )

    for page_name in WIKI_MECHANIC_PAGES:
        try:
            response = httpx.get(
                WIKI_API,
                params={
                    "action": "parse",
                    "page": page_name,
                    "prop": "wikitext",
                    "format": "json",
                    "formatversion": "2",
                },
                timeout=30.0,
                verify=False,
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                print(f"[WARN] Wiki page '{page_name}' not found: {data['error']}")
                time.sleep(WIKI_RATE_LIMIT_SECONDS)
                continue

            wikitext: str = data.get("parse", {}).get("wikitext", "")
            if not wikitext:
                time.sleep(WIKI_RATE_LIMIT_SECONDS)
                continue

            sections = _split_wikitext_sections(wikitext, page_name)
            docs.extend(sections)
            print(f"[INFO] '{page_name}': {len(sections)} secciones indexadas.")

        except Exception as e:
            print(f"[ERROR] Failed to fetch '{page_name}': {e}")
        finally:
            time.sleep(WIKI_RATE_LIMIT_SECONDS)

    return docs


def _split_wikitext_sections(wikitext: str, page_name: str) -> list[IngestDocument]:
    import re

    clean = re.sub(r"\{\{[^}]+\}\}", "", wikitext)
    clean = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", clean)
    clean = re.sub(r"'''|''", "", clean)

    h2_pattern = re.compile(r"^==\s*(.+?)\s*==$", re.MULTILINE)
    h2_matches = list(h2_pattern.finditer(clean))

    if not h2_matches:
        content = clean[:2000].strip()
        return [
            IngestDocument(
                doc_id=f"mechanic_{page_name.lower()}_intro",
                content=f"{page_name}: {content}",
                doc_type="mechanic",
                parent_content=f"{page_name}: {content}",
                metadata={
                    "doc_type": "mechanic",
                    "page": page_name,
                    "section": "intro",
                    "parent_section": page_name,
                },
            ),
        ]

    result: list[IngestDocument] = []
    for i, match in enumerate(h2_matches):
        section_title = match.group(1)
        section_start = match.end()
        section_end = (
            h2_matches[i + 1].start() if i + 1 < len(h2_matches) else len(clean)
        )
        section_text = clean[section_start:section_end].strip()

        if not section_text or len(section_text) < 50:
            continue

        parent_content = f"{page_name} - {section_title}:\n{section_text[:2000]}"
        chunk_content = f"{page_name} - {section_title}: {section_text[:800]}"

        result.append(
            IngestDocument(
                doc_id=f"mechanic_{page_name.lower()}_{section_title.lower().replace(' ', '_')}",
                content=chunk_content,
                doc_type="mechanic",
                parent_content=parent_content,
                metadata={
                    "doc_type": "mechanic",
                    "page": page_name,
                    "section": section_title,
                    "parent_section": page_name,
                },
            ),
        )

    return result


# ── Función de ingesta principal ─────────────────────────────────────────────


def ingest_all(force: bool = False) -> None:
    from fastembed import SparseTextEmbedding
    from qdrant_client.http.models import (
        Distance,
        PointStruct,
        SparseVector,
        SparseVectorParams,
        VectorParams,
    )

    from app.core.settings import get_settings
    from app.features.butler.llm.factory import get_embedding_model
    from app.features.butler.rag.client import get_qdrant_client

    settings = get_settings()
    collection = settings.qdrant_collection
    client = get_qdrant_client()

    collections = [c.name for c in client.get_collections().collections]
    if collection in collections and not force:
        count = client.count(collection_name=collection).count
        if count > 0:
            print(
                f"[INFO] Colección '{collection}' ya tiene {count} puntos. "
                "Usa --force para reindexar.",
            )
            return

    if collection in collections:
        client.delete_collection(collection)

    client.create_collection(
        collection_name=collection,
        vectors_config={
            "dense": VectorParams(size=DENSE_DIM, distance=Distance.COSINE),
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams(),
        },
    )
    print(f"[INFO] Colección '{collection}' creada.")

    print("[INFO] Construyendo documentos de ítems...")
    item_docs = build_item_documents()
    print(f"[INFO] {len(item_docs)} documentos de ítems.")

    print("[INFO] Construyendo documentos de mobs...")
    mob_docs = build_mob_documents()
    print(f"[INFO] {len(mob_docs)} documentos de mobs.")

    print("[INFO] Construyendo documentos de mecánicas (wiki)...")
    mechanic_docs = build_mechanic_documents()
    print(f"[INFO] {len(mechanic_docs)} documentos de mecánicas.")

    all_docs = item_docs + mob_docs + mechanic_docs
    print(f"[INFO] Total: {len(all_docs)} documentos a indexar.")

    embedding_model = get_embedding_model()
    sparse_model = SparseTextEmbedding(
        model_name="Qdrant/bm42-all-minilm-l6-v2-attentions",
    )

    for batch_start in range(0, len(all_docs), BATCH_SIZE):
        batch = all_docs[batch_start : batch_start + BATCH_SIZE]
        texts = [doc.content for doc in batch]

        dense_vectors = embedding_model.embed_documents(texts)
        sparse_results = list(sparse_model.embed(texts))

        points: list[PointStruct] = []
        for i, doc in enumerate(batch):
            sparse_vec = sparse_results[i]
            payload: dict[str, Any] = {
                "content": doc.content,
                "doc_type": doc.doc_type,
                **doc.metadata,
            }
            if doc.parent_content:
                payload["parent_content"] = doc.parent_content

            points.append(
                PointStruct(
                    id=batch_start + i,
                    vector={
                        "dense": dense_vectors[i],
                        "sparse": SparseVector(
                            indices=sparse_vec.indices.tolist(),
                            values=sparse_vec.values.tolist(),
                        ),
                    },
                    payload=payload,
                ),
            )

        client.upsert(collection_name=collection, points=points)
        print(
            f"[INFO] Batch {batch_start // BATCH_SIZE + 1}: {len(points)} puntos subidos.",
        )

    total = client.count(collection_name=collection).count
    print(f"[OK] Ingesta completada. Total en colección: {total} puntos.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestar datos Minecraft en Qdrant")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reindexar aunque ya existan datos",
    )
    args = parser.parse_args()
    ingest_all(force=args.force)
