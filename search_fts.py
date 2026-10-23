
from __future__ import annotations

import os
import re
import sqlite3

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "crm.db")

RESULT_TYPES = ('contacts', 'tasks', 'documents', 'wiki_pages', 'wiki_entries')

SNIPPET_START = '\x01'
SNIPPET_END = '\x02'


def _db_path() -> str:
    return os.environ.get("STELLWERK_DB_PATH", DEFAULT_DB_PATH)


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(_db_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=5000")
    return con


def _fts_match_expr(raw_query: str) -> str:
    tokens = re.findall(r"\w+", raw_query)
    if not tokens:
        return ""
    return " ".join(f'"{t}"*' for t in tokens)


def _run(con: sqlite3.Connection, sql: str, params: tuple) -> list[dict]:
    try:
        rows = con.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []
    return [{"id": r["id"], "snippet": r["snippet"]} for r in rows]


def search_all(query_text: str, include_archived: bool = False, limit_per_type: int = 20) -> dict:
    result: dict[str, list[dict]] = {t: [] for t in RESULT_TYPES}

    fts_query = _fts_match_expr((query_text or "").strip())
    if not fts_query:
        return result

    con = _connect()
    try:
        archived_filter = "" if include_archived else "AND (c.archived = 0 OR c.archived IS NULL)"
        result["contacts"] = _run(con, f"""
            SELECT c.id AS id, snippet(contacts_fts, -1, '{SNIPPET_START}', '{SNIPPET_END}', '…', 12) AS snippet
            FROM contacts_fts JOIN contacts c ON c.id = contacts_fts.rowid
            WHERE contacts_fts MATCH ? {archived_filter}
            ORDER BY rank LIMIT ?
        """, (fts_query, limit_per_type))

        result["tasks"] = _run(con, f"""
            SELECT t.id AS id, snippet(tasks_fts, -1, '{SNIPPET_START}', '{SNIPPET_END}', '…', 12) AS snippet
            FROM tasks_fts JOIN tasks t ON t.id = tasks_fts.rowid
            WHERE tasks_fts MATCH ?
            ORDER BY rank LIMIT ?
        """, (fts_query, limit_per_type))

        result["documents"] = _run(con, f"""
            SELECT d.id AS id, snippet(documents_fts, -1, '{SNIPPET_START}', '{SNIPPET_END}', '…', 12) AS snippet
            FROM documents_fts JOIN documents d ON d.id = documents_fts.rowid
            WHERE documents_fts MATCH ?
            ORDER BY rank LIMIT ?
        """, (fts_query, limit_per_type))

        result["wiki_pages"] = _run(con, f"""
            SELECT wp.id AS id, snippet(wiki_pages_fts, -1, '{SNIPPET_START}', '{SNIPPET_END}', '…', 12) AS snippet
            FROM wiki_pages_fts JOIN wiki_pages wp ON wp.id = wiki_pages_fts.rowid
            WHERE wiki_pages_fts MATCH ?
            ORDER BY rank LIMIT ?
        """, (fts_query, limit_per_type))

        result["wiki_entries"] = _run(con, f"""
            SELECT we.id AS id, snippet(wiki_entries_fts, -1, '{SNIPPET_START}', '{SNIPPET_END}', '…', 12) AS snippet
            FROM wiki_entries_fts JOIN wiki_entries we ON we.id = wiki_entries_fts.rowid
            WHERE wiki_entries_fts MATCH ?
            ORDER BY rank LIMIT ?
        """, (fts_query, limit_per_type))
    finally:
        con.close()

    return result


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "test"
    for typ, hits in search_all(q).items():
        print(f"-- {typ} ({len(hits)}) --")
        for h in hits:
            print(f"  #{h['id']}: {h['snippet']!r}")
