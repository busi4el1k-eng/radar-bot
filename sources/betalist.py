"""BetaList — startup-uri în (pre-)lansare, prezentate zilnic.

Titlurile din feed au forma „Nume – tagline”; despărțim numele de tagline,
iar restul detaliilor (imagine, descriere) vin din og:-urile paginii.
"""

import re

from .base import RawItem, RssSource

TITLE_SPLIT_RE = re.compile(r"\s+[–—-]\s+")


class BetaList(RssSource):
    name = "betalist"
    display_name = "BetaList"
    priority = 3
    kind = "product"
    feed_candidates = ["https://feeds.feedburner.com/BetaList"]

    def entry_to_item(self, entry) -> RawItem | None:
        item = super().entry_to_item(entry)
        if item is None:
            return None
        parts = TITLE_SPLIT_RE.split(item.title, maxsplit=1)
        if len(parts) == 2:
            item.title = parts[0].strip()
            tagline = parts[1].strip()
            # summary-ul din feed e doar HTML de navigare — tagline-ul e mai util
            item.summary = tagline
        return item
