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


def _fold(text: str) -> str:
    """lowercase + fără diacritice, ca „finanțare” și „finantare” să fie egale."""
    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def keyword_score(title: str, summary: str) -> float:
    text = _fold(f"{title} {summary}")
    score = sum(POSITIVE_WEIGHT for kw in POSITIVE_SIGNALS if _fold(kw) in text)
    score -= sum(NEGATIVE_WEIGHT for kw in NEGATIVE_SIGNALS if _fold(kw) in text)
    return score


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


SYSTEM_PROMPT = """Ești filtrul de conținut al unui canal Telegram care prezintă startup-uri românești și moldovenești.
Primești titlul și rezumatul unui articol de presă. Răspunde DOAR cu un obiect JSON:
{"relevant": true sau false, "descriere": "..." sau null}

"relevant" este true DOAR dacă articolul e despre un startup sau produs tech CONCRET, românesc sau moldovenesc:
lansare de produs, rundă de finanțare (seed, pre-seed, serie A...), achiziție, expansiune, campanie de crowdfunding.
Sunt false: granturi guvernamentale generice, fonduri europene pentru IMM-uri, conferințe, evenimente,
programe de accelerare care deschid înscrieri, interviuri generice, opinii, analize de piață, politică.

Dacă relevant=true, "descriere" = o descriere în română de MAXIM 300 de caractere, ton neutru-entuziast,
fără clickbait, fără emoji, care spune ce face startupul și care e noutatea.
Dacă relevant=false, "descriere" = null."""


async def ai_evaluate(title: str, summary: str) -> tuple[bool, str | None]:
    """Întoarce (relevant, draft_descriere). La orice eroare API, itemul trece
    mai departe pe baza scorului de cuvinte-cheie (fail-open), fără draft AI."""
    try:
        response = await _get_client().chat.completions.create(
            model=os.getenv("AI_MODEL", "gpt-4o-mini"),
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=250,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Titlu: {title}\nRezumat: {summary[:800]}"},
            ],
        )
        data = json.loads(response.choices[0].message.content)
        description = data.get("descriere") or None
        if description and len(description) > 300:
            description = description[:297] + "..."
        return bool(data.get("relevant")), description
    except Exception as exc:
        logger.warning(
            "Filtrul AI a eșuat (%s) — păstrez itemul pe baza scorului de cuvinte-cheie.",
            exc,
        )
        return True, None
