"""Filtrarea relevanței: scor pe cuvinte-cheie + (opțional) clasificare AI.

Scorul pe cuvinte-cheie rulează întotdeauna și e pragul de intrare.
Dacă USE_AI_FILTER=true și OPENAI_API_KEY e setat, itemele care trec pragul
sunt verificate și de un model OpenAI ieftin, care generează și draftul de
descriere în română. Calibrare: ajustează THRESHOLD sau listele de mai jos —
itemele filtrate apar în log cu scorul lor.
"""

import json
import logging
import os
import unicodedata

logger = logging.getLogger(__name__)

# Semnale pozitive/negative — comparate fără diacritice, cu lowercase.
POSITIVE_SIGNALS = [
    "startup",
    "a lansat",
    "lanseaza",
    "finantare",
    "runda",
    "seed",
    "pre-seed",
    "a atras",
    "investitie",
    "aplicatia",
    "platforma",
    "fondat de",
    "founder",
    "raises",
    "launches",
    "funding",
]

NEGATIVE_SIGNALS = [
    "grant guvernamental",
    "fonduri europene pentru imm",
    "conferinta",
    "eveniment",
    "program de accelerare deschide inscrieri",
    "interviu",
    "opinie",
    "analiza",
]

POSITIVE_WEIGHT = 1.0
NEGATIVE_WEIGHT = 1.5
THRESHOLD = 1.0

# Pentru sursele de tip "product" (GitHub Trending, Product Hunt) totul e în
# principiu un produs — filtrăm doar ce sigur NU e produs: liste, tutoriale...
PRODUCT_NEGATIVE_SIGNALS = [
    "awesome",
    "curated list",
    "list of",
    "collection of",
    "tutorial",
    "course",
    "interview questions",
    "roadmap",
    "cheatsheet",
    "cheat sheet",
    "study guide",
    "learning path",
    "free books",
    "book list",
    "coding challenges",
]


def _fold(text: str) -> str:
    """lowercase + fără diacritice, ca „finanțare” și „finantare” să fie egale."""
    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def keyword_score(title: str, summary: str) -> float:
    text = _fold(f"{title} {summary}")
    score = sum(POSITIVE_WEIGHT for kw in POSITIVE_SIGNALS if _fold(kw) in text)
    score -= sum(NEGATIVE_WEIGHT for kw in NEGATIVE_SIGNALS if _fold(kw) in text)
    return score


def product_score(title: str, summary: str) -> float:
    """Scor pentru sursele "product": pornește de la 2.0 (trece pragul) și
    scade la semnalele de ne-produs (liste, cursuri, tutoriale)."""
    text = _fold(f"{title} {summary[:300]}")
    score = 2.0
    score -= sum(2.0 for kw in PRODUCT_NEGATIVE_SIGNALS if _fold(kw) in text)
    return score


def score_for(kind: str, title: str, summary: str) -> float:
    if kind == "product":
        return product_score(title, summary)
    return keyword_score(title, summary)


# ── Filtrul AI (opțional) ────────────────────────────────────────────────────

def ai_enabled() -> bool:
    return (
        os.getenv("USE_AI_FILTER", "false").lower() in ("1", "true", "da", "yes")
        and bool(os.getenv("OPENAI_API_KEY"))
    )


_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import AsyncOpenAI

        _client = AsyncOpenAI()
    return _client


NEWS_PROMPT = """Ești filtrul de conținut al unui canal Telegram care prezintă startup-uri românești și moldovenești.
Primești titlul și rezumatul unui articol de presă. Răspunde DOAR cu un obiect JSON:
{"relevant": true sau false, "descriere": "..." sau null}

"relevant" este true DOAR dacă articolul e despre un startup sau produs tech CONCRET, românesc sau moldovenesc:
lansare de produs, rundă de finanțare (seed, pre-seed, serie A...), achiziție, expansiune, campanie de crowdfunding.
Sunt false: granturi guvernamentale generice, fonduri europene pentru IMM-uri, conferințe, evenimente,
programe de accelerare care deschid înscrieri, interviuri generice, opinii, analize de piață, politică.

Dacă relevant=true, "descriere" = o descriere în română de MAXIM 300 de caractere, ton neutru-entuziast,
fără clickbait, fără emoji, care spune ce face startupul și care e noutatea.
Dacă relevant=false, "descriere" = null."""

PRODUCT_PROMPT = """Ești redactorul unui canal Telegram care prezintă produse, unelte și startup-uri noi, în stil sec și informativ.
Primești numele produsului, descrierea lui și un fragment din README/pagina lui. Răspunde DOAR cu un obiect JSON:
{"relevant": true sau false, "descriere": "..." sau null}

"relevant" este false dacă NU e un produs/unealtă/startup concret, adică dacă e: o listă sau colecție
(awesome list), un tutorial, un curs, un roadmap de învățare, o culegere de exemple/exerciții/întrebări
de interviu, o carte sau documentație. Altfel, true.

Dacă relevant=true, scrie "descriere" în ROMÂNĂ, cu EXACT această structură (paragrafe separate prin linie goală):
1. Prima frază: esența produsului — ce este, fără a repeta numele (începe direct cu esența, ex: „alternativă self-hosted la Airtable, care transformă baza de date în...").
2. Un paragraf: din ce constă și ce face concret (funcții principale, cu ce se integrează).
3. Un paragraf care începe cu „— ”: ce problemă rezolvă și avantajul cheie.

Total maxim 550 de caractere. Ton sec, fără clickbait, fără emoji, fără superlative goale.
Dacă relevant=false, "descriere" = null."""


async def ai_evaluate(title: str, summary: str, kind: str = "news") -> tuple[bool, str | None]:
    """Întoarce (relevant, draft_descriere). La orice eroare API, itemul trece
    mai departe pe baza scorului de cuvinte-cheie (fail-open), fără draft AI."""
    is_product = kind == "product"
    max_len = 600 if is_product else 300
    try:
        response = await _get_client().chat.completions.create(
            model=os.getenv("AI_MODEL", "gpt-4o-mini"),
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=450 if is_product else 250,
            messages=[
                {"role": "system", "content": PRODUCT_PROMPT if is_product else NEWS_PROMPT},
                {
                    "role": "user",
                    "content": f"Nume/Titlu: {title}\nDescriere/Rezumat: {summary[:1500 if is_product else 800]}",
                },
            ],
        )
        data = json.loads(response.choices[0].message.content)
        description = data.get("descriere") or None
        if description and len(description) > max_len:
            description = description[: max_len - 3] + "..."
        return bool(data.get("relevant")), description
    except Exception as exc:
        logger.warning(
            "Filtrul AI a eșuat (%s) — păstrez itemul pe baza scorului de cuvinte-cheie.",
            exc,
        )
        return True, None
