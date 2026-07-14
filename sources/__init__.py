"""Registrul surselor agregatorului.

Ca să DEZACTIVEZI o sursă: comentează linia ei din ACTIVE_SOURCES.
Ca să ADAUGI o sursă: creezi un fișier nou în sources/ cu o clasă care
moștenește Source sau RssSource, apoi o adaugi în listă. Atât.
"""

from .base import HttpClient, RawItem, RssSource, Source
from .eustartups import EuStartups
from .logospress import LogosPress
from .newsmaker import NewsMaker
from .seedblink import SeedBlink
from .startarium import Startarium
from .startupcafe import StartupCafe
from .startupmoldova import StartupMoldova
from .startupro import StartUpRo
from .therecursive import TheRecursive

ACTIVE_SOURCES: list[type[Source]] = [
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

# slug -> nume afișat în postări („Sursa: ...”)
SOURCE_NAMES: dict[str, str] = {cls.name: cls.display_name for cls in ACTIVE_SOURCES}

# slug -> prioritate la deduplicare (mai mic = câștigă)
SOURCE_PRIORITIES: dict[str, int] = {cls.name: cls.priority for cls in ACTIVE_SOURCES}
