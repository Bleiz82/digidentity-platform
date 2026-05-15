"""
Stub embedding per Phase 1 — nessuna chiamata API reale.

Strategia: hash deterministico del testo → seed numpy → vettore casuale
normalizzato. Signal boosts controllati su dimensioni fisse per rendere
i ranking qualitativamente testabili:
  - LIFESTYLE_DIMS (0–49): boostati per testi lifestyle
  - FEATURES_DIMS (50–99): boostati per testi features strutturate
  - CONTENT_DIMS (100–149): boostati per testi content narrativo

Due vettori dello stesso "tipo" (es. due lifestyle con boost) avranno
alta cosine similarity tra loro e con query dello stesso tipo.
"""
import hashlib
from typing import Literal

import numpy as np

EMBEDDING_DIM = 3072

LIFESTYLE_DIMS = list(range(0, 50))
FEATURES_DIMS = list(range(50, 100))
CONTENT_DIMS = list(range(100, 150))
SIGNAL_BOOST = 2.0


EmbeddingType = Literal["content", "lifestyle", "features", "neutral"]


def _text_to_seed(text: str) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest, 16) % (2**32)


def make_stub_embedding(
    text: str,
    embedding_type: EmbeddingType = "neutral",
    dim: int = EMBEDDING_DIM,
) -> list[float]:
    """
    Genera embedding stub deterministico.

    - text: testo sorgente (renderizzato dal template)
    - embedding_type: determina quali dimensioni ricevono il signal boost
    - dim: dimensionalità (default 3072 per halfvec)
    """
    seed = _text_to_seed(text)
    rng = np.random.default_rng(seed)
    v = rng.random(dim).astype(np.float32)

    if embedding_type == "lifestyle":
        for d in LIFESTYLE_DIMS:
            v[d % dim] += SIGNAL_BOOST
    elif embedding_type == "features":
        for d in FEATURES_DIMS:
            v[d % dim] += SIGNAL_BOOST
    elif embedding_type == "content":
        for d in CONTENT_DIMS:
            v[d % dim] += SIGNAL_BOOST

    norm = np.linalg.norm(v)
    if norm > 0:
        v = v / norm

    return v.astype(np.float16).tolist()


def make_query_embedding(
    query_text: str,
    query_type: EmbeddingType = "neutral",
    dim: int = EMBEDDING_DIM,
) -> list[float]:
    """Alias esplicito per query (stessa logica, naming distinto)."""
    return make_stub_embedding(query_text, embedding_type=query_type, dim=dim)
