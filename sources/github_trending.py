"""GitHub Trending — produse/unelte open-source în plină ascensiune.

Parsează pagina de trending, apoi ia detaliile din API-ul GitHub (descriere,
stele, procentele limbajelor) și un fragment din README pentru draftul AI.
API-ul neautentificat are limită de 60 cereri/oră — de aceea sărim peste
repo-urile deja văzute în DB și limităm la MAX_REPOS per pull. Opțional,
GITHUB_TOKEN în .env ridică limita la 5000/oră.
"""

import logging
import os
import re

from bs4 import BeautifulSoup

import db
from .base import RawItem, Source

logger = logging.getLogger(__name__)

TRENDING_URL = "https://github.com/trending?since=daily"
API_BASE = "https://api.github.com"


class GitHubTrending(Source):
    name = "github"
    display_name = "GitHub Trending"
    priority = 1
    kind = "product"
    MAX_REPOS = 15

    def _api_headers(self) -> dict:
        token = os.getenv("GITHUB_TOKEN", "").strip()
        return {"Authorization": f"Bearer {token}"} if token else {}

    async def _api_get(self, path: str):
        resp = await self.http.get(f"{API_BASE}{path}")
        if resp is None:
            return None
        if resp.status_code == 403:
            logger.warning("Limita API GitHub atinsă — continui doar cu datele din pagină.")
            return "rate_limited"
        if resp.status_code != 200:
            return None
        return resp.json()

    async def fetch(self) -> list[RawItem]:
        resp = await self.http.get(TRENDING_URL)
        if resp is None or resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("article.Box-row")

        # sărim peste repo-urile deja văzute, ca să nu ardem limita API degeaba
        candidates: list[tuple[str, str]] = []
        for row in rows:
            anchor = row.select_one("h2 a[href]")
            if not anchor:
                continue
            repo_path = anchor["href"].strip("/")
            if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo_path):
                continue
            desc_el = row.select_one("p")
            description = desc_el.get_text(" ", strip=True) if desc_el else ""
            candidates.append((repo_path, description))

        urls = [f"https://github.com/{path}" for path, _ in candidates]
        known = await db.scraped_known_urls(urls)

        items: list[RawItem] = []
        rate_limited = False
        for repo_path, description in candidates:
            url = f"https://github.com/{repo_path}"
            if url in known:
                continue
            if len(items) >= self.MAX_REPOS:
                break
            items.append(
                await self._build_item(repo_path, description, skip_api=rate_limited)
            )
            if items[-1].meta.get("rate_limited"):
                rate_limited = True
        return items

    async def _build_item(
        self, repo_path: str, description: str, skip_api: bool = False
    ) -> RawItem:
        owner, _, repo = repo_path.partition("/")
        title = repo
        meta: dict = {}

        if not skip_api:
            data = await self._api_get(f"/repos/{repo_path}")
            if data == "rate_limited":
                meta["rate_limited"] = True
            elif isinstance(data, dict):
                title = data.get("name") or repo
                description = data.get("description") or description
                meta["stars"] = data.get("stargazers_count")
                if data.get("homepage"):
                    meta["homepage"] = data["homepage"]
                langs = await self._api_get(f"/repos/{repo_path}/languages")
                if isinstance(langs, dict) and langs:
                    total = sum(langs.values()) or 1
                    top = sorted(langs.items(), key=lambda kv: -kv[1])[:3]
                    meta["languages"] = {
                        lang: round(size * 100 / total, 1) for lang, size in top
                    }

        readme = ""
        readme_resp = await self.http.get(
            f"https://raw.githubusercontent.com/{repo_path}/HEAD/README.md"
        )
        if readme_resp is not None and readme_resp.status_code == 200:
            readme = readme_resp.text[:2000]

        summary = description
        if readme:
            summary = f"{description}\n\nREADME:\n{readme}"

        return RawItem(
            source=self.name,
            title=title,
            url=f"https://github.com/{repo_path}",
            summary=summary[:2500],
            image_url=f"https://opengraph.githubassets.com/1/{repo_path}",
            meta=meta,
        )
