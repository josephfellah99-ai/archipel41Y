"""RAG : découpage des documents, embeddings et recherche hybride (vectorielle + lexicale).

L'embedding par défaut (« local-hash-v1 ») est calculé sur le poste, hors ligne et
sans service externe : hachage de termes et de bigrammes normalisés, pondération
TF sous-linéaire, vecteur L2-normalisé de 768 dimensions. Un fournisseur
d'embeddings (OpenAI, Mistral, Ollama…) peut être utilisé à la place.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass

from ..document_analysis.numbers import fold

LOCAL_MODEL = "local-hash-v1"
DIM = 768
STOP = set("""a au aux avec ce ces dans de des du elle en et eux il je la le les leur lui ma mais me meme mes moi mon
ne nos notre nous on ou par pas pour qu que qui sa se ses son sur ta te tes toi ton tu un une vos votre vous c d j l
m n s t y est sont ete etre avoir a ont fait faire plus tout tous toute toutes cette cet sans sous entre comme
dont si ni car donc or the of and to in is""".split())


def tokenize(text: str) -> list[str]:
    t = re.sub(r"[^a-z0-9/,.%²³ ]+", " ", fold(text))
    out = []
    for w in t.split():
        w = w.strip(".,")
        if len(w) < 2 or w in STOP:
            continue
        if w.isalpha() and len(w) > 4 and w.endswith(("s", "x")):
            w = w[:-1]
        out.append(w)
    return out


def _h(term: str) -> tuple[int, float]:
    d = hashlib.blake2b(term.encode(), digest_size=8).digest()
    idx = int.from_bytes(d[:4], "little") % DIM
    sign = 1.0 if d[4] & 1 else -1.0
    return idx, sign


def local_embed(text: str) -> list[float]:
    toks = tokenize(text)
    feats = Counter(toks)
    feats.update(f"{a}_{b}" for a, b in zip(toks, toks[1:]))
    vec = [0.0] * DIM
    for term, tf in feats.items():
        idx, sign = _h(term)
        weight = (1 + math.log(tf)) * (1.4 if "_" in term else 1.0)
        vec[idx] += sign * weight
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


@dataclass
class Chunk:
    index: int
    page: int | None
    text: str


HEADING_RX = re.compile(r"^\s*(article|art\.|chapitre|titre|section|zone|lot)\b|^\s*\d{1,2}(\.\d{1,2}){0,3}\.?\s+[A-ZÉÈÀ]", re.I)
CONTEXT_RX = re.compile(r"^\s*(zone|chapitre|titre|lot|partie)\b", re.I)


def chunk_pages(pages: list[tuple[int | None, str]], size: int = 750, overlap: int = 120) -> list[Chunk]:
    """Découpe en passages d'environ `size` caractères.

    Les intitulés (article, chapitre, zone, lot…) ouvrent un nouveau passage, et le dernier
    intitulé de contexte (ex. « ZONE UB ») est rappelé en tête des passages suivants :
    chaque passage reste ainsi interprétable isolément (indispensable pour un règlement de PLU)."""
    chunks: list[Chunk] = []
    for page, text in pages:
        lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
        buf, context = "", ""

        def flush():
            nonlocal buf
            body = buf.strip()
            if body:
                prefix = f"[{context}] " if context and not body.startswith(context) else ""
                chunks.append(Chunk(len(chunks), page, (prefix + body)[: int(size * 1.8)]))
            buf = ""

        expanded = []
        for line in lines:  # lignes très longues (texte sans retour à la ligne) : découpage avec recouvrement
            while len(line) > size:
                cut = line.rfind(" ", int(size * 0.6), size)
                cut = cut if cut > 0 else size
                expanded.append(line[:cut])
                line = line[max(0, cut - overlap):]
            expanded.append(line)
        for line in expanded:
            is_heading = bool(HEADING_RX.match(line)) and len(line) < 140
            if is_heading and len(buf) > 150:
                flush()
            if CONTEXT_RX.match(line) and len(line) < 140:
                context = line[:100]
            if len(buf) + len(line) + 1 > size and buf:
                tail = buf[-overlap:]
                flush()
                buf = tail
            buf = (buf + "\n" + line) if buf else line
        flush()
    return chunks


def lexical_score(query_tokens: list[str], text: str) -> float:
    """Couverture des termes de la question + bonus pour les expressions (bigrammes) retrouvées telles quelles."""
    if not query_tokens:
        return 0.0
    toks_list = tokenize(text)
    toks = Counter(toks_list)
    q = set(query_tokens)
    hits = sum(1 + math.log(toks[t]) for t in q if toks.get(t))
    coverage = sum(1 for t in q if toks.get(t)) / len(q)
    qb = set(zip(query_tokens, query_tokens[1:]))
    bigrams = len(qb & set(zip(toks_list, toks_list[1:]))) if qb else 0
    return hits / (len(q) + 0.5) + coverage + 0.5 * bigrams


def hybrid_rank(query: str, candidates: list[dict], query_vec: list[float] | None, k: int = 8) -> list[dict]:
    """candidates : [{text, embedding, ...}] → les k meilleurs avec score combiné."""
    qt = tokenize(query)
    scored = []
    for c in candidates:
        vs = cosine(query_vec, c.get("embedding")) if query_vec and c.get("embedding") else 0.0
        ls = lexical_score(qt, c["text"])
        score = 0.45 * vs + 0.55 * min(1.0, ls / 3.0)
        if score > 0.05:
            scored.append({**c, "score": round(score, 4)})
    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[:k]
