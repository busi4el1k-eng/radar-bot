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
    logger.info("Baza de date e pregătită (tabelul submissions există).")


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
