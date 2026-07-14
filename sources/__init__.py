"""Registrul surselor agregatorului.

Ca să DEZACTIVEZI o sursă: comentează linia ei din ACTIVE_SOURCES.
Ca să ADAUGI o sursă: creezi un fișier nou în sources/ cu o clasă care
moștenește Source sau RssSource, apoi o adaugi în listă. Atât.

Două tipuri de surse (atributul `kind`):
- "product": produsul în sine (GitHub Trending, Product Hunt) — postare sec,
  cu ce face și ce rezolvă
- "news": articole de presă despre startup-uri (sursele vechi RO/MD,
  dezactivate acum — decomentează-le dacă le vrei înapoi)
"""

from .base import HttpClient, RawItem, RssSource, Source
from .betalist import BetaList
from .eustartups import EuStartups
from .github_trending import GitHubTrending
from .logospress import LogosPress
from .newsmaker import NewsMaker
from .producthunt import ProductHunt
from .seedblink import SeedBlink
from .startarium import Startarium
from .startupcafe import StartupCafe
from .startupmoldova import StartupMoldova
from .startupro import StartUpRo
from .therecursive import TheRecursive

ACTIVE_SOURCES: list[type[Source]] = [
    ProductHunt,
    BetaList,
    # GitHubTrending,  # unelte open-source trending — dezactivat: nu-s mereu startap-uri
    # ── surse de presă RO/MD, dezactivate (stil newsletter) ──
    # TheRecursive,
    # StartupCafe,
    # StartUpRo,
    # Startarium,
    # EuStartups,
    # StartupMoldova,
    # NewsMaker,
    # LogosPress,
    # SeedBlink,
]

_ALL_SOURCES: list[type[Source]] = [
    GitHubTrending,
    ProductHunt,
    BetaList,
    TheRecursive,
    StartupCafe,
    StartUpRo,
    Startarium,
    EuStartups,
    StartupMoldova,
    NewsMaker,
    LogosPress,
    SeedBlink,
]

# slug -> nume afișat (toate sursele, ca statisticile vechi să rămână lizibile)
SOURCE_NAMES: dict[str, str] = {cls.name: cls.display_name for cls in _ALL_SOURCES}

# slug -> prioritate la deduplicare (mai mic = câștigă)
SOURCE_PRIORITIES: dict[str, int] = {cls.name: cls.priority for cls in _ALL_SOURCES}

# slug -> tipul sursei ("product" / "news")
SOURCE_KINDS: dict[str, str] = {cls.name: cls.kind for cls in _ALL_SOURCES}
