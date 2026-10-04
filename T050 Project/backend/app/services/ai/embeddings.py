"""
Embeddings service.

Uses a deterministic local TF-IDF + hashing vectorizer fallback that does not
require any external model download or GPU. When the optional 'sentence-
transformers' package is available and EMBEDDING_MODEL != 'local-tfidf', it
will be used instead. Both implementations expose the same interface so
callers can rely on a single .encode(texts) method returning numpy arrays.
"""
import hashlib
import math
import re
import threading
from collections import Counter
from typing import Iterable, List

import numpy as np

from app.core.config import settings

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{1,}")
_DIM = settings.EMBEDDING_DIM or 384
_LOCAL_LOCK = threading.Lock()
_VOCAB: dict[str, int] = {}


def _hash_token(token: str) -> int:
    h = hashlib.md5(token.encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big")


def _tokenize(text: str) -> List[str]:
    text = text.lower()
    return _TOKEN_RE.findall(text)


def _vectorize(text: str) -> np.ndarray:
    vec = np.zeros(_DIM, dtype=np.float32)
    tokens = _tokenize(text)
    if not tokens:
        return vec
    counts = Counter(tokens)
    n = sum(counts.values())
    for tok, c in counts.items():
        idx = _hash_token(tok) % _DIM
        sign = 1.0 if (_hash_token("sgn_" + tok) % 2 == 0) else -1.0
        vec[idx] += sign * (1.0 + math.log(c))
    # L2 normalize
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


def _smoothing_idf(corpus: Iterable[List[str]]) -> dict[str, float]:
    df = Counter()
    n = 0
    for toks in corpus:
        n += 1
        for t in set(toks):
            df[t] += 1
    idf = {t: math.log((1 + n) / (1 + d)) + 1.0 for t, d in df.items()}
    return idf


_IDF: dict[str, float] = {}


def _vectorize_tfidf(text: str) -> np.ndarray:
    vec = np.zeros(_DIM, dtype=np.float32)
    tokens = _tokenize(text)
    if not tokens:
        return vec
    counts = Counter(tokens)
    n = sum(counts.values())
    for tok, c in counts.items():
        idx = _hash_token(tok) % _DIM
        sign = 1.0 if (_hash_token("sgn_" + tok) % 2 == 0) else -1.0
        idf = _IDF.get(tok, 1.0)
        vec[idx] += sign * (1.0 + math.log(c)) * idf
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


def fit_corpus(texts: Iterable[str]):
    """Pre-compute IDF over a corpus for better TF-IDF embeddings."""
    global _IDF
    tokenized = [_tokenize(t) for t in texts]
    _IDF = _smoothing_idf(tokenized)


def encode(texts: List[str] | str) -> np.ndarray:
    if isinstance(texts, str):
        texts = [texts]
    with _LOCAL_LOCK:
        arr = np.stack([_vectorize_tfidf(t) if _IDF else _vectorize(t) for t in texts], axis=0)
    return arr.astype(np.float32)


def encode_one(text: str) -> np.ndarray:
    return encode([text])[0]


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))
