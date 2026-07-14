"""Stratul de bază de date: PostgreSQL (Neon) prin asyncpg.

Un singur pool global, cu reîncercare automată la erorile de conexiune —
Neon poate suspenda instanța la inactivitate, iar prima interogare după
trezire poate pica cu o eroare de conexiune.
"""

import asyncio
import logging

import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS submissions (
    id             SERIAL PRIMARY KEY,
    user_id        BIGINT      NOT NULL,
    username       TEXT,
    product_name   TEXT        NOT NULL,
    description    TEXT        NOT NULL,
    link           TEXT        NOT NULL,
    contact        TEXT        NOT NULL,
    photo_file_id  TEXT        NOT NULL,
    status         TEXT        NOT NULL DEFAULT 'pending',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

CREATE_SCRAPED_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS scraped_items (
    id                   SERIAL PRIMARY KEY,
    source               TEXT        NOT NULL,
    title                TEXT        NOT NULL,
    url                  TEXT        NOT NULL UNIQUE,
    extra_urls           JSONB       NOT NULL DEFAULT '[]',
    published_at         TIMESTAMPTZ,
    summary              TEXT,
    draft_description    TEXT,
    image_url            TEXT,
    photo_file_id        TEXT,
    relevance_score      REAL,
    status               TEXT        NOT NULL DEFAULT 'new',
    published_message_id BIGINT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

_RETRYABLE = (
    asyncpg.PostgresConnectionError,
    asyncpg.InterfaceError,
    ConnectionError,
    TimeoutError,
    OSError,
)


async def init(database_url: str) -> None:
    """Creează pool-ul de conexiuni și tabelul, cu reîncercări la pornire."""
    global _pool
    for attempt in range(1, 6):
        try:
            _pool = await asyncpg.create_pool(
                dsn=database_url, min_size=1, max_size=5, command_timeout=30
            )
            break
        except _RETRYABLE as exc:
            if attempt == 5:
                raise
            logger.warning(
                "Conectarea la baza de date a eșuat (încercarea %d/5): %s — reîncerc în 3s",
                attempt,
                exc,
            )
            await asyncio.sleep(3)
    async with _pool.acquire() as conn:
        await conn.execute(CREATE_TABLE_SQL)
        await conn.execute(CREATE_SCRAPED_TABLE_SQL)
    logger.info("Baza de date e pregătită (tabelele submissions și scraped_items există).")


async def close() -> None:
    if _pool is not None:
        await _pool.close()


async def _run(method: str, query: str, *args):
    """Rulează o interogare cu reîncercare la erorile de conexiune."""
    last_exc = None
    for attempt in range(1, 4):
        try:
            async with _pool.acquire() as conn:
                return await getattr(conn, method)(query, *args)
        except _RETRYABLE as exc:
            last_exc = exc
            logger.warning(
                "Eroare de conexiune la baza de date (încercarea %d/3): %s",
                attempt,
                exc,
            )
            await asyncio.sleep(attempt)
    raise last_exc


async def create_submission(
    user_id: int,
    username: str | None,
    product_name: str,
    description: str,
    link: str,
    contact: str,
    photo_file_id: str,
) -> int:
    return await _run(
        "fetchval",
        """
        INSERT INTO submissions
            (user_id, username, product_name, description, link, contact, photo_file_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
        """,
        user_id,
        username,
        product_name,
        description,
        link,
        contact,
        photo_file_id,
    )


async def get_submission(sub_id: int) -> asyncpg.Record | None:
    return await _run("fetchrow", "SELECT * FROM submissions WHERE id = $1", sub_id)


async def get_pending(limit: int = 10) -> list[asyncpg.Record]:
    return await _run(
        "fetch",
        "SELECT * FROM submissions WHERE status = 'pending' ORDER BY created_at LIMIT $1",
        limit,
    )


async def count_pending() -> int:
    return await _run(
        "fetchval", "SELECT count(*) FROM submissions WHERE status = 'pending'"
    )


async def last_recent_submission_at(user_id: int):
    """created_at al ultimei submisii active (nerespinse) din ultimele 7 zile, sau None.

    Submisiile respinse nu blochează — fondatorul poate corecta și retrimite.
    """
    return await _run(
        "fetchval",
        """
        SELECT created_at FROM submissions
        WHERE user_id = $1
          AND status <> 'rejected'
          AND created_at > now() - interval '7 days'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        user_id,
    )


async def claim(sub_id: int, new_status: str) -> asyncpg.Record | None:
    """Schimbă atomic statusul unei submisii aflate în 'pending'.

    Întoarce rândul actualizat sau None dacă submisia era deja procesată
    (protecție când doi admini apasă butoanele în același timp).
    """
    return await _run(
        "fetchrow",
        """
        UPDATE submissions SET status = $2
        WHERE id = $1 AND status = 'pending'
        RETURNING *
        """,
        sub_id,
        new_status,
    )


async def set_status(sub_id: int, status: str) -> None:
    await _run("execute", "UPDATE submissions SET status = $2 WHERE id = $1", sub_id, status)


# ── scraped_items (agregatorul) ──────────────────────────────────────────────


async def insert_scraped_item(
    source: str,
    title: str,
    url: str,
    extra_urls: str,
    published_at,
    summary: str,
    draft_description: str,
    image_url: str | None,
    relevance_score: float,
) -> int | None:
    """Inserează un item nou; None dacă URL-ul există deja."""
    return await _run(
        "fetchval",
        """
        INSERT INTO scraped_items
            (source, title, url, extra_urls, published_at, summary,
             draft_description, image_url, relevance_score)
        VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9)
        ON CONFLICT (url) DO NOTHING
        RETURNING id
        """,
        source,
        title,
        url,
        extra_urls,
        published_at,
        summary,
        draft_description,
        image_url,
        relevance_score,
    )


async def scraped_known_urls(urls: list[str]) -> set[str]:
    if not urls:
        return set()
    rows = await _run(
        "fetch", "SELECT url FROM scraped_items WHERE url = ANY($1::text[])", urls
    )
    return {row["url"] for row in rows}


async def recent_scraped_titles(days: int = 30) -> list[asyncpg.Record]:
    return await _run(
        "fetch",
        "SELECT id, title FROM scraped_items WHERE created_at > now() - make_interval(days => $1)",
        days,
    )


async def append_extra_urls(item_id: int, urls: list[str]) -> None:
    if not urls:
        return
    import json

    await _run(
        "execute",
        "UPDATE scraped_items SET extra_urls = extra_urls || $2::jsonb WHERE id = $1",
        item_id,
        json.dumps(urls),
    )


async def get_scraped(item_id: int) -> asyncpg.Record | None:
    return await _run("fetchrow", "SELECT * FROM scraped_items WHERE id = $1", item_id)


async def next_inbox_item(after_id: int = 0) -> asyncpg.Record | None:
    """Următorul item cu status 'new' după id-ul dat; revine la început dacă
    nu mai e nimic după el (răsfoire circulară)."""
    row = await _run(
        "fetchrow",
        "SELECT * FROM scraped_items WHERE status = 'new' AND id > $1 ORDER BY id LIMIT 1",
        after_id,
    )
    if row is None and after_id:
        row = await _run(
            "fetchrow",
            "SELECT * FROM scraped_items WHERE status = 'new' AND id <> $1 ORDER BY id LIMIT 1",
            after_id,
        )
    return row


async def count_inbox_new() -> int:
    return await _run(
        "fetchval", "SELECT count(*) FROM scraped_items WHERE status = 'new'"
    )


async def claim_scraped(item_id: int, new_status: str) -> asyncpg.Record | None:
    """Schimbă atomic statusul unui item 'new' (protecție la dublu-click)."""
    return await _run(
        "fetchrow",
        """
        UPDATE scraped_items SET status = $2
        WHERE id = $1 AND status = 'new'
        RETURNING *
        """,
        item_id,
        new_status,
    )


async def set_scraped_status(
    item_id: int, status: str, published_message_id: int | None = None
) -> None:
    await _run(
        "execute",
        "UPDATE scraped_items SET status = $2, published_message_id = COALESCE($3, published_message_id) WHERE id = $1",
        item_id,
        status,
        published_message_id,
    )


async def update_scraped_draft(item_id: int, draft: str) -> None:
    await _run(
        "execute",
        "UPDATE scraped_items SET draft_description = $2 WHERE id = $1",
        item_id,
        draft,
    )


async def update_scraped_photo(item_id: int, photo_file_id: str) -> None:
    await _run(
        "execute",
        "UPDATE scraped_items SET photo_file_id = $2 WHERE id = $1",
        item_id,
        photo_file_id,
    )


async def inbox_stats() -> list[asyncpg.Record]:
    return await _run(
        "fetch",
        """
        SELECT source, status, count(*) AS total
        FROM scraped_items
        GROUP BY source, status
        ORDER BY source, status
        """,
    )
