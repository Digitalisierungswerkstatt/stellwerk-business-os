
from __future__ import annotations

import os
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import umlaut_lint
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "crm.db")


def _db_path() -> str:
    return os.environ.get("STELLWERK_DB_PATH", DEFAULT_DB_PATH)



BOARD_STAGE_KEYS = ("backlog", "todo", "in_arbeit", "review", "erledigt")
VALID_PRIORITIES = ("hoch", "mittel", "niedrig")
DONE_STATUS = "erledigt"
CLOSED_STATUSES = ("erledigt", "done")
OPEN_STATUSES = ("backlog", "todo", "in_arbeit", "review")
VALID_STATUSES_FOR_CREATE = ("backlog", "todo", "in_arbeit")

PRIORITY_SCORES = {"hoch": 3, "mittel": 2, "niedrig": 1}
IMPACT_SCORES = {"hoch": 3, "mittel": 2, "niedrig": 1}
EFFORT_SCORES = {"xs": 1, "s": 2, "m": 3, "l": 5, "xl": 8}

RECURRENCE_SPAWN_FIELDS = frozenset({
    "title", "description", "status", "priority", "effort", "impact",
    "category", "due_date", "contact_id", "created_by", "recurrence_days",
    "position",
})
RECURRENCE_CREATED_BY = "System"

QUOTE_STATUS_KEYS = ("draft", "sent", "accepted", "converted", "rejected", "expired", "cancelled")
INVOICE_STATUS_KEYS = ("draft", "sent", "paid", "overdue", "cancelled")
INCOMING_INVOICE_STATUS_KEYS = ("open", "paid", "cancelled")
PAYMENT_METHOD_KEYS = ("sepa", "kreditkarte", "lastschrift", "paypal", "bar", "privateinlage", "sonstiges")
UNIT_KEYS = ("Einmalig", "Monatlich", "Pro Kanal", "Stunde", "Pauschal")
BILLING_TYPE_KEYS = ("onetime", "recurring")
CONTACT_TYPE_KEYS = ("customer", "supplier", "both")
BANK_MATCH_STATUS_KEYS = ("unmatched", "suggested", "confirmed", "ignored")

INVOICE_PAID_FROM_STATUSES = ("sent", "overdue")

TAETIGKEIT_KONTAKT_KEYS = (
    "anbahnung", "vorgespraeche", "angebotserstellung", "onboarding", "meetings",
    "beratung", "keywordrecherche", "inhaltserstellung", "entwicklung", "menuefuehrung",
    "setup_tracking", "setup_seo_geo", "setup_reporting", "setup_zielgruppen",
    "setup_kanalstrategie", "setup_google_ads", "setup_meta_ads", "setup_microsoft_ads",
    "pflege_google_ads", "pflege_meta_ads", "kontaktpflege", "administration",
)
TAETIGKEIT_ALLGEMEIN_KEYS = (
    "stellwerk", "tooling", "fundament_kundenarbeit", "marketing_eigenes",
    "akquise", "netzwerken", "weiterbildung", "buchhaltung", "sonstiges",
)
TAETIGKEIT_KEYS = TAETIGKEIT_KONTAKT_KEYS + TAETIGKEIT_ALLGEMEIN_KEYS

QUOTE_ALLOWED_UNITS = ("Einmalig", "Monatlich", "Jaehrlich", "Jährlich",
                       "Quartalsweise", "Stunden")
QUOTE_ALLOWED_BILLING_TYPES = ("onetime", "recurring")

def _incoming_pdf_dir() -> str:
    return os.environ.get(
        "STELLWERK_UPLOADS_DIR",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "incoming_invoices"),
    )

ABRECHNUNGS_TAETIGKEITEN = (
    "buchhaltung", "rechnungsstellung", "abrechnung", "mahnung", "mahnwesen",
)
ABRECHNUNGSMODELL_KEYS = (
    "retainer", "retainer_trueup", "stundenbasis", "projekt_fix",
    "agentur_partner", "aufwand_extern", "pro_bono",
    "lead_quote", "paused", "lost", "intern",
)
REGIE_MODELLE = ("retainer_trueup", "stundenbasis")
SELF_TRACKING_MODELLE = ("retainer", "projekt_fix", "pro_bono",
                         "agentur_partner", "aufwand_extern")
NOTIZ_BLACKLIST = (
    "walkthrough", "step-by-step begleitet", "begleitet", "mit max",
    "aufgebaut mit", "durchgegangen", "vorbereitet fuer max",
    "vorbereitet für max", "ki-gestuetzt", "ki-gestützt",
    "claude-gestuetzt", "claude-gestützt",
)



@dataclass
class WriteResult:

    ok: bool
    committed: bool
    row_id: int | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: str = ""
    meta: dict = field(default_factory=dict)

    def report(self) -> str:
        lines: list[str] = []
        if self.summary:
            lines.append(self.summary)
        for w in self.warnings:
            lines.append(f"[WARN]  {w}")
        for e in self.errors:
            lines.append(f"[FEHLER] {e}")
        return "\n".join(lines)


def _ro_conn() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{_db_path()}?mode=ro", uri=True)
    con.execute("PRAGMA busy_timeout=5000")
    return con


def _rw_conn() -> sqlite3.Connection:
    con = sqlite3.connect(_db_path())
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=5000")
    return con


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def check_umlauts(*texts: str | None) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    seen: set[str] = set()
    for text in texts:
        if not text:
            continue
        for gefunden, korrekt in umlaut_lint.find_ascii_umlauts(text):
            if gefunden in seen:
                continue
            seen.add(gefunden)
            hits.append((gefunden, korrekt))
    return hits


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def contact_label(contact_id: int | None) -> str | None:
    if contact_id is None:
        return None
    con = _ro_conn()
    try:
        row = con.execute(
            "SELECT organisation, vorname, nachname FROM contacts WHERE id = ?",
            (contact_id,),
        ).fetchone()
    finally:
        con.close()
    if not row:
        return None
    org, vor, nach = row
    person = " ".join(p for p in (vor, nach) if p).strip()
    if org and person:
        return f"{org} / {person}"
    return org or person or None


def contact_exists(contact_id: int) -> bool:
    return contact_label(contact_id) is not None


def contact_abrechnungsmodell(contact_id: int) -> str | None:
    con = _ro_conn()
    try:
        row = con.execute(
            "SELECT abrechnungsmodell FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()
    finally:
        con.close()
    return row[0] if row else None


def _fetch_task(task_id: int):
    con = _ro_conn()
    try:
        return con.execute(
            "SELECT id, title, status, priority, due_date, contact_id, recurrence_days "
            "FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    finally:
        con.close()


def _task_score(priority: str | None, effort: str | None, impact: str | None) -> float | None:
    if not impact or not effort:
        return None
    try:
        return (IMPACT_SCORES[impact] * PRIORITY_SCORES[priority]) / EFFORT_SCORES[effort]
    except KeyError:
        return None


RECURRENCE_CALENDAR_MONTHS = {30: 1, 90: 3}


def next_recurrence_date(base: date, recurrence_days: int) -> date:
    months = RECURRENCE_CALENDAR_MONTHS.get(int(recurrence_days))
    if not months:
        return base + timedelta(days=int(recurrence_days))
    y, m = divmod(base.month - 1 + months, 12)
    y, m = base.year + y, m + 1
    last_day = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)).day
    return date(y, m, min(base.day, last_day))


def recurrence_label(recurrence_days: int) -> str:
    months = RECURRENCE_CALENDAR_MONTHS.get(int(recurrence_days))
    return {1: "monatlich", 3: "quartalsweise"}.get(months, f"alle {recurrence_days} Tage")


def _next_recurrence_due(due_date, recurrence_days: int) -> str:
    base = None
    if due_date:
        try:
            base = datetime.strptime(str(due_date)[:10], "%Y-%m-%d").date()
        except ValueError:
            base = None
    return next_recurrence_date(base or date.today(), recurrence_days).isoformat()


def _spawn_recurring_task_on(con: sqlite3.Connection, task_id: int) -> tuple[int | None, str | None]:
    row = con.execute(
        "SELECT title, description, priority, effort, impact, category, "
        "due_date, contact_id, recurrence_days FROM tasks WHERE id = ?",
        (task_id,),
    ).fetchone()
    if row is None:
        return None, None
    (title, description, priority, effort, impact, category,
     due_date, contact_id, recurrence_days) = row
    if not recurrence_days:
        return None, None

    new_due = _next_recurrence_due(due_date, recurrence_days)
    max_pos = con.execute(
        "SELECT COALESCE(MAX(position), -1) FROM tasks WHERE status = 'todo'"
    ).fetchone()[0]
    now = _now()

    cur = con.execute(
        "INSERT INTO tasks (title, description, status, priority, effort, impact, "
        "score, category, due_date, contact_id, created_by, created_at, updated_at, "
        "position, recurrence_days) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (title, description, "todo", priority, effort, impact,
         _task_score(priority, effort, impact), category, new_due, contact_id,
         RECURRENCE_CREATED_BY, now, now, max_pos + 1, recurrence_days),
    )
    new_id = cur.lastrowid

    for (tag,) in con.execute(
        "SELECT tag FROM task_tags WHERE task_id = ?", (task_id,)
    ).fetchall():
        con.execute(
            "INSERT INTO task_tags (task_id, tag) VALUES (?, ?)", (new_id, tag)
        )

    return new_id, new_due


def close_task(task_id: int, *, commit: bool = False) -> WriteResult:
    try:
        task_id = int(task_id)
    except (TypeError, ValueError):
        return WriteResult(ok=False, committed=False,
                           errors=[f"Ungueltige Task-ID: {task_id!r}"])

    row = _fetch_task(task_id)
    if row is None:
        return WriteResult(ok=False, committed=False, row_id=task_id,
                           errors=[f"Task #{task_id} existiert nicht."])

    _id, title, status, priority, due_date, contact_id, recurrence_days = row

    if status in CLOSED_STATUSES:
        return WriteResult(
            ok=False, committed=False, row_id=task_id,
            warnings=[f"Task #{task_id} ist bereits '{status}'. Kein Write."],
            summary=f"Task #{task_id}: {title}",
        )

    summary = f"Task #{task_id}: {title}\n  Status: {status} -> {DONE_STATUS}"
    if recurrence_days:
        summary += (f"\n  Wiederkehr {recurrence_label(recurrence_days)} -> Folge-Task "
                    f"(todo, faellig {_next_recurrence_due(due_date, recurrence_days)})")

    if not commit:
        return WriteResult(ok=True, committed=False, row_id=task_id,
                           summary="VORSCHAU schliessen:\n" + summary,
                           meta={"recurrence_days": recurrence_days})

    con = _rw_conn()
    try:
        cur = con.execute(
            "UPDATE tasks SET status = ?, completed_at = ?, updated_at = ? WHERE id = ?",
            (DONE_STATUS, _now(), _now(), task_id),
        )
        if cur.rowcount != 1:
            con.rollback()
            return WriteResult(ok=False, committed=False, row_id=task_id,
                               errors=[f"Erwartete 1 Zeile, {cur.rowcount} betroffen — Rollback."])
        spawned_id, spawned_due = _spawn_recurring_task_on(con, task_id)
        con.commit()
    except sqlite3.Error as exc:
        con.rollback()
        return WriteResult(ok=False, committed=False, row_id=task_id,
                           errors=[f"DB-Fehler beim Schliessen von #{task_id}: {exc}"])
    finally:
        con.close()

    summary = f"Task #{task_id} geschlossen ('{DONE_STATUS}'):\n  {title}"
    if spawned_id:
        summary += (f"\n  Wiederkehr: Folge-Task #{spawned_id} angelegt "
                    f"(todo, faellig {spawned_due})")
    return WriteResult(ok=True, committed=True, row_id=task_id, summary=summary,
                       meta={"spawned_task_id": spawned_id, "spawned_due_date": spawned_due})


def _insert_task_on(con: sqlite3.Connection, *, title: str, status: str, priority: str,
                    due_date: str | None, contact_id: int | None, category: str | None,
                    description: str | None, created_by: str) -> int:
    cur = con.execute(
        "INSERT INTO tasks (title, status, priority, due_date, contact_id, "
        "category, description, created_by, position, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)",
        (title, status, priority, due_date, contact_id, category, description,
         created_by, _now(), _now()),
    )
    return cur.lastrowid


def create_task(
    title: str,
    *,
    priority: str = "mittel",
    status: str = "todo",
    due_date: str | None = None,
    contact_id: int | None = None,
    category: str | None = None,
    description: str | None = None,
    created_by: str = "Max",
    commit: bool = False,
) -> WriteResult:
    errors: list[str] = []

    title = (title or "").strip()
    if not title:
        errors.append("Titel ist Pflicht und darf nicht leer sein.")
    if len(title) > 500:
        errors.append(f"Titel zu lang ({len(title)} > 500 Zeichen).")

    if priority not in VALID_PRIORITIES:
        errors.append(f"priority '{priority}' ungueltig. Erlaubt: {', '.join(VALID_PRIORITIES)}.")
    if status not in VALID_STATUSES_FOR_CREATE:
        errors.append(f"status '{status}' ungueltig fuer neuen Task. Erlaubt: "
                      f"{', '.join(VALID_STATUSES_FOR_CREATE)}.")

    if due_date is not None:
        try:
            datetime.strptime(due_date, "%Y-%m-%d")
        except ValueError:
            errors.append(f"due_date '{due_date}' nicht im Format YYYY-MM-DD.")

    if contact_id is not None:
        try:
            contact_id = int(contact_id)
        except (TypeError, ValueError):
            errors.append(f"contact_id '{contact_id}' ist keine Zahl.")
        else:
            if not contact_exists(contact_id):
                errors.append(f"contact_id {contact_id} existiert nicht in contacts.")

    umlaut_hits = check_umlauts(title, description, category)
    for bad, good in umlaut_hits:
        errors.append(f"Umlaut-Typo '{bad}' -> '{good}'. Korrigieren vor dem Anlegen.")

    if errors:
        return WriteResult(ok=False, committed=False, errors=errors)

    kontakt = contact_label(contact_id)
    summary_lines = [f"Titel: {title}", f"  Status: {status} · Prioritaet: {priority}"]
    if due_date:
        summary_lines.append(f"  Faellig: {due_date}")
    if kontakt:
        summary_lines.append(f"  Kontakt: {kontakt} (id={contact_id})")
    if category:
        summary_lines.append(f"  Kategorie: {category}")
    if description:
        summary_lines.append(f"  Beschreibung: {description[:120]}")
    summary = "\n".join(summary_lines)

    if not commit:
        return WriteResult(ok=True, committed=False, summary="VORSCHAU neuer Task:\n" + summary)

    con = _rw_conn()
    try:
        new_id = _insert_task_on(con, title=title, status=status, priority=priority, due_date=due_date,
                                 contact_id=contact_id, category=category, description=description,
                                 created_by=created_by)
        con.commit()
    finally:
        con.close()

    return WriteResult(ok=True, committed=True, row_id=new_id,
                       summary=f"Task #{new_id} angelegt:\n{summary}")


def create_task_comment(
    task_id: int,
    content: str,
    *,
    author: str = "Claude",
    commit: bool = False,
) -> WriteResult:
    try:
        task_id = int(task_id)
    except (TypeError, ValueError):
        return WriteResult(ok=False, committed=False,
                           errors=[f"Ungueltige Task-ID: {task_id!r}"])

    content = (content or "").strip()
    if not content:
        return WriteResult(ok=False, committed=False, row_id=task_id,
                           errors=["Kommentar ist leer."])

    row = _fetch_task(task_id)
    if row is None:
        return WriteResult(ok=False, committed=False, row_id=task_id,
                           errors=[f"Task #{task_id} existiert nicht."])
    title = row[1]

    umlaut_hits = check_umlauts(content, author)
    if umlaut_hits:
        return WriteResult(
            ok=False, committed=False, row_id=task_id,
            errors=[f"ASCII-Umlaut '{found}' in '{ctx}' — echte Umlaute schreiben."
                    for found, ctx in umlaut_hits],
        )

    preview = content if len(content) <= 300 else content[:300] + " […]"
    summary = f"Task #{task_id}: {title}\n  Autor: {author}\n  Kommentar: {preview}"

    if not commit:
        return WriteResult(ok=True, committed=False, row_id=task_id,
                           summary="VORSCHAU Kommentar:\n" + summary)

    con = _rw_conn()
    try:
        cur = con.execute(
            "INSERT INTO task_comments (task_id, author, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (task_id, author, content, _now()),
        )
        new_id = cur.lastrowid
        con.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", (_now(), task_id))
        con.commit()
    except sqlite3.Error as exc:
        con.rollback()
        return WriteResult(ok=False, committed=False, row_id=task_id,
                           errors=[f"DB-Fehler beim Kommentieren von #{task_id}: {exc}"])
    finally:
        con.close()

    return WriteResult(ok=True, committed=True, row_id=new_id,
                       summary=f"Kommentar #{new_id} an Task #{task_id} gehaengt:\n{summary}",
                       meta={"task_id": task_id})


SNAPSHOT_ANLAESSE = ("stuendlich", "job_start", "job_ende", "manuell")
FUELL_JOBS = ("A", "B", "C", "D")
FUELL_MODI = ("halbautomatisch", "automatisch")
FUELL_ENDSTATUS = ("fertig", "abgebrochen")
FUELL_ITEM_AKTIONEN = ("erledigt", "vorbereitet", "uebersprungen", "idee_neu",
                       "einwand_beantwortet", "nachkontrolle", "seite_gebaut",
                       "kommentar_statt_idee", "idee_bewertet",
                       "gegenstand_neu", "gegenstand_notiz")
FUELL_LOCK_STUNDEN = 3
FUELL_KOMMENTAR_PRAEFIX = "[Füll-Job]"
FUELL_TAG_STUFE3 = "füll-job:stufe3"
FUELL_TAGS = (FUELL_TAG_STUFE3,)


def record_limit_snapshots(rows, anlass: str, *, commit: bool = False) -> WriteResult:
    if anlass not in SNAPSHOT_ANLAESSE:
        return WriteResult(ok=False, committed=False,
                           errors=[f"anlass '{anlass}' ungueltig. Erlaubt: {', '.join(SNAPSHOT_ANLAESSE)}."])
    rows = list(rows or [])
    if not rows:
        return WriteResult(ok=False, committed=False, errors=["Keine Messzeilen."])
    taken_at = _now()
    zeilen = [f"  {r['profile']}: Woche {r.get('seven_day_pct')} % · 5 h {r.get('five_hour_pct')} %"
              + (f" · Fehler: {r['error']}" if r.get('error') else "") for r in rows]
    summary = f"Snapshot {taken_at} ({anlass}):\n" + "\n".join(zeilen)
    if not commit:
        return WriteResult(ok=True, committed=False, summary="VORSCHAU " + summary)
    con = _rw_conn()
    try:
        con.executemany(
            "INSERT INTO claude_limit_snapshots (taken_at, profile, account_uuid, five_hour_pct, "
            "seven_day_pct, seven_day_resets_at, error, anlass) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(taken_at, r['profile'], r.get('account_uuid'), r.get('five_hour_pct'),
              r.get('seven_day_pct'), r.get('seven_day_resets_at'), r.get('error'), anlass)
             for r in rows])
        con.commit()
    except sqlite3.Error as exc:
        con.rollback()
        return WriteResult(ok=False, committed=False, errors=[f"DB-Fehler beim Snapshot: {exc}"])
    finally:
        con.close()
    return WriteResult(ok=True, committed=True, summary=summary,
                       meta={"taken_at": taken_at, "anzahl": len(rows)})


def _fuell_lock_pruefen(con, jetzt: datetime):
    blockierend, verwaist = [], []
    for lid, started_at in con.execute(
            "SELECT id, started_at FROM fuell_jobs WHERE status = 'laeuft'").fetchall():
        alter = jetzt - datetime.fromisoformat(started_at)
        (blockierend if alter < timedelta(hours=FUELL_LOCK_STUNDEN) else verwaist).append((lid, started_at))
    return blockierend, verwaist


def start_fuell_job(job: str, profile: str, *, account_uuid: str | None = None,
                    budget_punkte: float | None = None, pct_before: float | None = None,
                    modus: str = "halbautomatisch", rolle_id: int | None = None,
                    gegenstand_id: int | None = None, commit: bool = False) -> WriteResult:
    errors = []
    if job not in FUELL_JOBS:
        errors.append(f"job '{job}' ungueltig. Erlaubt: {', '.join(FUELL_JOBS)}.")
    if modus not in FUELL_MODI:
        errors.append(f"modus '{modus}' ungueltig. Erlaubt: {', '.join(FUELL_MODI)}.")
    if not (profile or "").strip():
        errors.append("profile ist Pflicht.")
    if (rolle_id is not None or gegenstand_id is not None) and job != "B":
        errors.append("rolle_id und gegenstand_id gibt es nur bei Job B.")
    if errors:
        return WriteResult(ok=False, committed=False, errors=errors)

    jetzt = datetime.now()
    con = _ro_conn()
    try:
        blockierend, verwaist = _fuell_lock_pruefen(con, jetzt)
    finally:
        con.close()
    if blockierend:
        lid, seit = blockierend[0]
        return WriteResult(ok=False, committed=False,
                           errors=[f"Lauf #{lid} läuft seit {seit}. Kein zweiter Start."])

    summary = (f"Füll-Lauf Job {job} auf {profile} ({modus}), Budget {budget_punkte} Punkte, "
               f"Woche vorher {pct_before} %")
    if verwaist:
        summary += "\n  verwaiste Läufe werden abgebrochen: " + ", ".join(f"#{l}" for l, _ in verwaist)
    if not commit:
        return WriteResult(ok=True, committed=False, summary="VORSCHAU " + summary)

    con = _rw_conn()
    try:
        con.execute("BEGIN IMMEDIATE")
        blockierend, verwaist = _fuell_lock_pruefen(con, jetzt)
        if blockierend:
            con.rollback()
            lid, seit = blockierend[0]
            return WriteResult(ok=False, committed=False,
                               errors=[f"Lauf #{lid} läuft seit {seit}. Kein zweiter Start."])
        for lid, _ in verwaist:
            con.execute(
                "UPDATE fuell_jobs SET status = 'abgebrochen', ended_at = ?, "
                "pct_after = COALESCE(pct_after, (SELECT s.seven_day_pct FROM claude_limit_snapshots s "
                "WHERE s.profile = fuell_jobs.profile AND s.error IS NULL "
                "ORDER BY s.taken_at DESC LIMIT 1)), "
                "ergebnis = COALESCE(ergebnis, 'verwaist, beim nächsten Start abgebrochen') WHERE id = ?",
                (_now(), lid))
        cur = con.execute(
            "INSERT INTO fuell_jobs (job, profile, account_uuid, modus, started_at, pct_before, "
            "budget_punkte, status, rolle_id, gegenstand_id) VALUES (?, ?, ?, ?, ?, ?, ?, 'laeuft', ?, ?)",
            (job, profile, account_uuid, modus, _now(), pct_before, budget_punkte, rolle_id, gegenstand_id))
        new_id = cur.lastrowid
        con.commit()
    except sqlite3.Error as exc:
        con.rollback()
        return WriteResult(ok=False, committed=False, errors=[f"DB-Fehler beim Start: {exc}"])
    finally:
        con.close()
    return WriteResult(ok=True, committed=True, row_id=new_id,
                       summary=f"Lauf #{new_id} gestartet:\n  {summary}")


def finish_fuell_job(lauf_id: int, *, status: str, pct_after: float | None = None,
                     ergebnis: str | None = None, cursor: str | None = None,
                     commit: bool = False) -> WriteResult:
    if status not in FUELL_ENDSTATUS:
        return WriteResult(ok=False, committed=False,
                           errors=[f"status '{status}' ungueltig. Erlaubt: {', '.join(FUELL_ENDSTATUS)}."])
    ergebnis = (ergebnis or "").strip() or None
    hits = check_umlauts(ergebnis)
    if hits:
        return WriteResult(ok=False, committed=False,
                           errors=[f"Umlaut-Typo '{b}' -> '{g}'." for b, g in hits])
    con = _ro_conn()
    try:
        row = con.execute("SELECT id, job, status FROM fuell_jobs WHERE id = ?", (lauf_id,)).fetchone()
    finally:
        con.close()
    if row is None:
        return WriteResult(ok=False, committed=False, errors=[f"Lauf #{lauf_id} existiert nicht."])
    if row[2] != "laeuft":
        return WriteResult(ok=False, committed=False, row_id=lauf_id,
                           errors=[f"Lauf #{lauf_id} ist bereits '{row[2]}'."])
    summary = f"Lauf #{lauf_id} (Job {row[1]}) -> {status}, Woche nachher {pct_after} %"
    if ergebnis:
        summary += f"\n  Ergebnis: {ergebnis}"
    if not commit:
        return WriteResult(ok=True, committed=False, row_id=lauf_id, summary="VORSCHAU " + summary)
    con = _rw_conn()
    try:
        cur = con.execute(
            "UPDATE fuell_jobs SET status = ?, ended_at = ?, pct_after = ?, ergebnis = ?, "
            "cursor = COALESCE(?, cursor) WHERE id = ? AND status = 'laeuft'",
            (status, _now(), pct_after, ergebnis, cursor, lauf_id))
        if cur.rowcount != 1:
            con.rollback()
            return WriteResult(ok=False, committed=False, row_id=lauf_id,
                               errors=[f"Erwartete 1 Zeile, {cur.rowcount} betroffen. Rollback."])
        con.commit()
    except sqlite3.Error as exc:
        con.rollback()
        return WriteResult(ok=False, committed=False, errors=[f"DB-Fehler beim Beenden: {exc}"])
    finally:
        con.close()
    return WriteResult(ok=True, committed=True, row_id=lauf_id, summary=summary)


def _task_version(con, task_id: int):
    return con.execute("SELECT updated_at, description, status, title FROM tasks WHERE id = ?",
                       (task_id,)).fetchone()


def _beschreibung_hash(text) -> str:
    return hashlib.sha256((text or "").replace("\r\n", "\n").strip().encode("utf-8")).hexdigest()


def set_task_status(task_id: int, status: str | None = None, *, erwartet_updated_at: str,
                    kommentar: str | None = None, author: str = "Claude", tag: str | None = None,
                    fuell_job_id: int | None = None, aktion: str | None = None,
                    stufe: int | None = None, commit: bool = False) -> WriteResult:
    try:
        task_id = int(task_id)
    except (TypeError, ValueError):
        return WriteResult(ok=False, committed=False, errors=[f"Ungueltige Task-ID: {task_id!r}"])
    errors = []
    if status is not None and status not in OPEN_STATUSES:
        errors.append(f"status '{status}' hier nicht erlaubt. Erlaubt: {', '.join(OPEN_STATUSES)}; "
                      "schließen nur über close_task.")
    if tag is not None and tag not in FUELL_TAGS:
        errors.append(f"tag '{tag}' unbekannt. Erlaubt: {', '.join(FUELL_TAGS)}.")
    kommentar = (kommentar or "").strip() or None
    if status is None and kommentar is None and tag is None:
        errors.append("Nichts zu tun: weder Status, Kommentar noch Tag.")
    if fuell_job_id is not None:
        if aktion not in FUELL_ITEM_AKTIONEN:
            errors.append(f"aktion '{aktion}' ungueltig. Erlaubt: {', '.join(FUELL_ITEM_AKTIONEN)}.")
        if kommentar and not kommentar.startswith(FUELL_KOMMENTAR_PRAEFIX):
            kommentar = f"{FUELL_KOMMENTAR_PRAEFIX} {kommentar}"
    for bad, good in check_umlauts(kommentar, author):
        errors.append(f"Umlaut-Typo '{bad}' -> '{good}'.")
    if errors:
        return WriteResult(ok=False, committed=False, row_id=task_id, errors=errors)

    con = _ro_conn()
    try:
        row = _task_version(con, task_id)
        lauf = (con.execute("SELECT status FROM fuell_jobs WHERE id = ?", (fuell_job_id,)).fetchone()
                if fuell_job_id is not None else None)
    finally:
        con.close()
    if row is None:
        return WriteResult(ok=False, committed=False, row_id=task_id,
                           errors=[f"Task #{task_id} existiert nicht."])
    if fuell_job_id is not None and (lauf is None or lauf[0] != "laeuft"):
        return WriteResult(ok=False, committed=False, row_id=task_id,
                           errors=[f"Lauf #{fuell_job_id} läuft nicht."])
    if row[2] in CLOSED_STATUSES:
        return WriteResult(ok=False, committed=False, row_id=task_id,
                           errors=[f"Task #{task_id} ist bereits geschlossen."])
    aktuell_updated_at = row[0]
    if aktuell_updated_at != erwartet_updated_at:
        return WriteResult(ok=False, committed=False, row_id=task_id, errors=[
            f"Task #{task_id} wurde seit dem Lesen geändert ({erwartet_updated_at} -> "
            f"{aktuell_updated_at}). Liegen lassen."])

    summary = f"Task #{task_id}: {row[3]}\n  Status: {row[2]} -> {status or row[2]}"
    if tag:
        summary += f"\n  Tag: {tag}"
    if kommentar:
        summary += f"\n  Kommentar: {kommentar[:200]}"
    if not commit:
        return WriteResult(ok=True, committed=False, row_id=task_id, summary="VORSCHAU " + summary)

    con = _rw_conn()
    try:
        con.execute("BEGIN IMMEDIATE")
        row = _task_version(con, task_id)
        aktuell_updated_at = row[0]
        if aktuell_updated_at != erwartet_updated_at:
            con.rollback()
            return WriteResult(ok=False, committed=False, row_id=task_id, errors=[
                f"Task #{task_id} wurde seit dem Lesen geändert ({erwartet_updated_at} -> "
                f"{aktuell_updated_at}). Liegen lassen."])
        jetzt = _now()
        con.execute("UPDATE tasks SET status = COALESCE(?, status), updated_at = ? WHERE id = ?",
                    (status, jetzt, task_id))
        kommentar_id = None
        if kommentar:
            kommentar_id = con.execute(
                "INSERT INTO task_comments (task_id, author, content, created_at) VALUES (?, ?, ?, ?)",
                (task_id, author, kommentar, jetzt)).lastrowid
        if tag:
            con.execute("INSERT OR IGNORE INTO task_tags (task_id, tag) VALUES (?, ?)", (task_id, tag))
        if fuell_job_id is not None:
            beschreibung_hash = _beschreibung_hash(row[1])
            con.execute(
                "INSERT INTO fuell_job_items (fuell_job_id, task_id, aktion, stufe, beschreibung_hash, "
                "kommentar_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (fuell_job_id, task_id, aktion, stufe, beschreibung_hash, kommentar_id, jetzt))
        con.commit()
    except sqlite3.Error as exc:
        con.rollback()
        return WriteResult(ok=False, committed=False, row_id=task_id,
                           errors=[f"DB-Fehler bei Task #{task_id}: {exc}"])
    finally:
        con.close()
    return WriteResult(ok=True, committed=True, row_id=task_id, summary=summary,
                       meta={"kommentar_id": kommentar_id, "updated_at": jetzt})


_CHECKBOX_RE = re.compile(r"^(\s*[-*] \[)([ xX])(\] )(.*?)(\r?\n?)$")


def check_task_item(task_id: int, punkt: str, *, commit: bool = False) -> WriteResult:
    try:
        task_id = int(task_id)
    except (TypeError, ValueError):
        return WriteResult(ok=False, committed=False,
                           errors=[f"Ungueltige Task-ID: {task_id!r}"])

    punkt = (punkt or "").strip()
    if not punkt:
        return WriteResult(ok=False, committed=False, row_id=task_id,
                           errors=["Punkt ist leer. Den Anfang des Checkbox-Texts angeben, z.B. \"0.3\"."])

    con = _ro_conn()
    try:
        row = con.execute("SELECT title, description FROM tasks WHERE id = ?",
                          (task_id,)).fetchone()
    finally:
        con.close()
    if row is None:
        return WriteResult(ok=False, committed=False, row_id=task_id,
                           errors=[f"Task #{task_id} existiert nicht."])
    title, description = row[0], row[1] or ""

    lines = description.splitlines(keepends=True)
    prefix_re = re.compile(re.escape(punkt) + r"(?=$|[\s:,;)])")
    boxes = [(i, m) for i, line in enumerate(lines)
             if (m := _CHECKBOX_RE.match(line))]
    hits = [(i, m) for i, m in boxes if prefix_re.match(m.group(4))]

    if not hits:
        offen = [m.group(4)[:80] for _, m in boxes if m.group(2) == " "]
        hint = ("Offene Punkte: " + " | ".join(offen)) if offen else "Die Beschreibung hat keine offene Checkbox."
        return WriteResult(ok=False, committed=False, row_id=task_id,
                           errors=[f"Keine Checkbox in #{task_id} beginnt mit {punkt!r}. {hint}"])
    if len(hits) > 1:
        return WriteResult(ok=False, committed=False, row_id=task_id,
                           errors=[f"{len(hits)} Checkboxen beginnen mit {punkt!r}, Punkt genauer angeben: "
                                   + " | ".join(m.group(4)[:80] for _, m in hits)])

    idx, m = hits[0]
    if m.group(2) != " ":
        return WriteResult(ok=False, committed=False, row_id=task_id,
                           warnings=[f"Bereits abgehakt, kein Write: {m.group(4)[:120]}"],
                           summary=f"Task #{task_id}: {title}")

    alt = lines[idx].rstrip("\r\n")
    lines[idx] = m.group(1) + "x" + m.group(3) + m.group(4) + m.group(5)
    neu_description = "".join(lines)
    summary = (f"Task #{task_id}: {title}\n  vorher:  {alt.strip()}\n"
               f"  nachher: {lines[idx].rstrip(chr(13) + chr(10)).strip()}")

    if not commit:
        return WriteResult(ok=True, committed=False, row_id=task_id,
                           summary="VORSCHAU abhaken:\n" + summary)

    con = _rw_conn()
    try:
        cur = con.execute(
            "UPDATE tasks SET description = ?, updated_at = ? WHERE id = ? AND description = ?",
            (neu_description, _now(), task_id, row[1]),
        )
        if cur.rowcount != 1:
            con.rollback()
            return WriteResult(ok=False, committed=False, row_id=task_id,
                               errors=[f"Die Beschreibung von #{task_id} wurde zwischen Lesen und "
                                       "Schreiben geaendert. Nichts geschrieben, erneut aufrufen."])
        con.commit()
    except sqlite3.Error as exc:
        con.rollback()
        return WriteResult(ok=False, committed=False, row_id=task_id,
                           errors=[f"DB-Fehler beim Abhaken in #{task_id}: {exc}"])
    finally:
        con.close()

    return WriteResult(ok=True, committed=True, row_id=task_id,
                       summary="Abgehakt:\n" + summary)


def _notiz_blacklist_hits(notiz: str) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    text = (notiz or "").lower()
    for token in NOTIZ_BLACKLIST:
        pattern = rf"(?:^|[\s.,;:!?(){{}}\[\]'\"-])({re.escape(token)})(?:$|[\s.,;:!?(){{}}\[\]'\"-])"
        m = re.search(pattern, text)
        if m:
            hits.append((token, m.group(1)))
    return hits


def lint_time_entry(
    contact_id: int,
    taetigkeit: str,
    notiz: str,
    *,
    abrechnungsmodell: str | None = None,
) -> dict:
    if abrechnungsmodell is None:
        abrechnungsmodell = contact_abrechnungsmodell(contact_id)

    blocks: list[str] = []
    warnings: list[str] = []

    t = (taetigkeit or "").lower()
    hit = next((n for n in ABRECHNUNGS_TAETIGKEITEN if n in t), None)
    if hit and abrechnungsmodell in REGIE_MODELLE:
        ziel = ("die naechste True-Up-Rechnung"
                if abrechnungsmodell == "retainer_trueup"
                else "die naechste Stundenabrechnung")
        blocks.append(
            f"Taetigkeit enthaelt '{hit}', Kunde hat abrechnungsmodell="
            f"'{abrechnungsmodell}'. Buchhaltung/Rechnungsstellung wuerde zirkulaer "
            f"in {ziel} wandern. Eintrag NICHT erfassen."
        )
    elif hit and abrechnungsmodell in SELF_TRACKING_MODELLE:
        warnings.append(
            f"Taetigkeit enthaelt '{hit}'. Auch bei abrechnungsmodell="
            f"'{abrechnungsmodell}' gehoert das in Unternehmer-Overhead, nicht in "
            f"time_entries. Empfehlung: Eintrag verwerfen."
        )

    is_self_tracking = abrechnungsmodell in SELF_TRACKING_MODELLE
    if is_self_tracking:
        warnings.append(
            f"abrechnungsmodell='{abrechnungsmodell}': time_entry dient nur "
            f"Self-Tracking (Rentabilitaets-Signal), niemals als offene Forderung "
            f"interpretieren."
        )

    notiz_hits = _notiz_blacklist_hits(notiz)
    if notiz_hits:
        tokens = ", ".join(f"'{t_}'" for t_, _ in notiz_hits)
        blocks.append(
            f"Notiz enthaelt Prozess-/Meta-Sprache: {tokens}. Zeiteintraege sind "
            f"Leistungsnachweis fuer Kunden — Notiz wie Rechnungs-Zeile formulieren."
        )

    decision = "block" if blocks else ("warn" if warnings else "pass")
    return {
        "decision": decision,
        "abrechnungsmodell": abrechnungsmodell,
        "is_self_tracking": is_self_tracking,
        "blocks": blocks,
        "warnings": warnings,
    }


def create_time_entry(
    contact_id: int,
    dauer_minuten: int,
    notiz: str,
    taetigkeit: str,
    *,
    datum: str | None = None,
    commit: bool = False,
    skip_umlaut_check: bool = False,
    abrechnungsmodell: str | None = None,
) -> WriteResult:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        contact_id = int(contact_id)
    except (TypeError, ValueError):
        return WriteResult(ok=False, committed=False,
                           errors=[f"contact_id '{contact_id}' ist keine Zahl."])
    if not contact_exists(contact_id):
        return WriteResult(ok=False, committed=False,
                           errors=[f"contact_id {contact_id} existiert nicht in contacts. "
                                   f"Kein Kontakt-Create im /zeit-Pfad."])

    try:
        dauer_minuten = int(dauer_minuten)
    except (TypeError, ValueError):
        errors.append(f"dauer_minuten '{dauer_minuten}' ist keine Zahl.")
    else:
        if dauer_minuten <= 0:
            errors.append(f"dauer_minuten muss > 0 sein (war {dauer_minuten}).")

    taetigkeit = (taetigkeit or "").strip()
    if not taetigkeit:
        errors.append("taetigkeit ist Pflicht und darf nicht leer sein.")
    elif taetigkeit not in TAETIGKEIT_KEYS:
        warnings.append(
            f"taetigkeit '{taetigkeit}' ist kein SSOT-Wert "
            f"(models.TAETIGKEIT_KONTAKT_OPTIONS/_ALLGEMEIN_OPTIONS). Freitext erlaubt, "
            f"aber das Reporting splittet ihn separat — bewusst? Sonst passenden Enum-Wert waehlen."
        )

    notiz = (notiz or "").strip()
    if not notiz:
        errors.append("notiz ist Pflicht und darf nicht leer sein.")

    if datum is None:
        datum = datetime.now().date().isoformat()
    else:
        try:
            datetime.strptime(datum, "%Y-%m-%d")
        except ValueError:
            errors.append(f"datum '{datum}' nicht im Format YYYY-MM-DD.")

    if not skip_umlaut_check:
        for bad, good in check_umlauts(notiz):
            errors.append(f"Umlaut-Typo in Notiz: '{bad}' -> '{good}'. Korrigieren vor Insert.")

    lint = lint_time_entry(contact_id, taetigkeit, notiz, abrechnungsmodell=abrechnungsmodell)
    errors.extend(f"Lint-BLOCK: {b}" for b in lint["blocks"])
    warnings.extend(lint["warnings"])

    meta = {
        "abrechnungsmodell": lint["abrechnungsmodell"],
        "is_self_tracking": lint["is_self_tracking"],
        "lint_decision": lint["decision"],
    }

    if errors:
        return WriteResult(ok=False, committed=False, errors=errors,
                           warnings=warnings, meta=meta)

    stunden = dauer_minuten / 60
    kontakt = contact_label(contact_id)
    summary = "\n".join([
        f"Kontakt: {kontakt} (id={contact_id})",
        f"  Datum: {datum} · Dauer: {dauer_minuten} Min ({stunden:.2f} h)",
        f"  Taetigkeit: {taetigkeit}",
        f"  Abrechnungsmodell: {lint['abrechnungsmodell'] or 'NULL (klaerungspflichtig)'}",
        f"  Notiz: {notiz}",
    ])

    if not commit:
        return WriteResult(ok=True, committed=False, warnings=warnings,
                           summary="VORSCHAU Zeiteintrag:\n" + summary, meta=meta)

    con = _rw_conn()
    try:
        cur = con.execute(
            "INSERT INTO time_entries (contact_id, datum, dauer_minuten, taetigkeit, "
            "notiz, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (contact_id, datum, dauer_minuten, taetigkeit, notiz, _now()),
        )
        new_id = cur.lastrowid
        con.commit()
    finally:
        con.close()

    return WriteResult(ok=True, committed=True, row_id=new_id, warnings=warnings,
                       summary=f"Zeiteintrag angelegt (id={new_id}):\n{summary}", meta=meta)


def _interaction_exists(con: sqlite3.Connection, contact_id: int, external_ref: str) -> bool:
    pattern = f"%{_escape_like(f'[msgid:{external_ref}]')}%"
    row = con.execute(
        "SELECT 1 FROM interactions WHERE contact_id = ? AND notiz LIKE ? ESCAPE '\\' LIMIT 1",
        (contact_id, pattern),
    ).fetchone()
    return row is not None


def create_interaction(
    contact_id: int,
    datum: str,
    betreff: str,
    preview: str,
    richtung: str,
    gegen_adresse: str,
    external_ref: str,
    *,
    typ: str = "E-Mail",
    commit: bool = False,
) -> WriteResult:
    errors: list[str] = []

    try:
        contact_id = int(contact_id)
    except (TypeError, ValueError):
        return WriteResult(ok=False, committed=False,
                           errors=[f"contact_id '{contact_id}' ist keine Zahl."])
    if not contact_exists(contact_id):
        return WriteResult(ok=False, committed=False,
                           errors=[f"contact_id {contact_id} existiert nicht. "
                                   f"Kein Kontakt-Create im E-Mail-Import."])

    external_ref = (external_ref or "").strip()
    if not external_ref:
        errors.append("external_ref (Message-ID) ist Pflicht — ohne sie keine Idempotenz.")

    richtung = (richtung or "").strip()
    if richtung not in ("Gesendet", "Empfangen"):
        errors.append(f"richtung '{richtung}' ungueltig (erwartet 'Gesendet' oder 'Empfangen').")

    if datum is None:
        errors.append("datum ist Pflicht.")
    else:
        try:
            datetime.strptime(datum, "%Y-%m-%d")
        except (TypeError, ValueError):
            errors.append(f"datum '{datum}' nicht im Format YYYY-MM-DD.")

    if errors:
        return WriteResult(ok=False, committed=False, errors=errors)

    betreff = (betreff or "").strip()
    gegen_adresse = (gegen_adresse or "").strip()
    prefix = (f"Gesendet an {gegen_adresse}" if richtung == "Gesendet"
              else f"Empfangen von {gegen_adresse}")
    betreff_line = f"{prefix}: {betreff}" if betreff else f"{prefix}: (kein Betreff)"

    body = (preview or "").strip()
    notiz_parts = [betreff_line]
    if body:
        notiz_parts.append(body)
    notiz_parts.append(f"[msgid:{external_ref}]")
    notiz = "\n\n".join(notiz_parts)

    kontakt = contact_label(contact_id)
    summary = (f"{betreff_line}\n"
               f"  Kontakt: {kontakt} (id={contact_id}) · Datum: {datum} · typ: {typ}")

    con = _ro_conn()
    try:
        if _interaction_exists(con, contact_id, external_ref):
            return WriteResult(ok=True, committed=False, meta={"skipped": True},
                               summary=f"SKIP (bereits importiert): {betreff_line}")
    finally:
        con.close()

    if not commit:
        return WriteResult(ok=True, committed=False,
                           meta={"skipped": False, "notiz": notiz},
                           summary="VORSCHAU interaction:\n" + summary)

    con = _rw_conn()
    try:
        if _interaction_exists(con, contact_id, external_ref):
            return WriteResult(ok=True, committed=False, meta={"skipped": True},
                               summary=f"SKIP (bereits importiert): {betreff_line}")
        cur = con.execute(
            "INSERT INTO interactions (contact_id, datum, typ, notiz, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (contact_id, datum, typ, notiz, _now_sql()),
        )
        new_id = cur.lastrowid
        con.commit()
    finally:
        con.close()

    return WriteResult(ok=True, committed=True, row_id=new_id, meta={"skipped": False},
                       summary=f"interaction #{new_id} angelegt:\n{summary}")


def _now_sql() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


_NUMBER_SOURCES = {
    "R": ("documents", "number", "doc_type = 'invoice' AND number LIKE 'R-%'"),
    "H": ("documents", "number", "doc_type = 'invoice' AND number LIKE 'H-%'"),
    "A": ("documents", "number", "doc_type = 'quote' AND number LIKE 'A-%'"),
    "E": ("incoming_invoices", "number", "number LIKE 'E-%'"),
    "K": ("contacts", "customer_number", "customer_number LIKE 'K-%'"),
}


def _next_number_on(con: sqlite3.Connection, prefix: str) -> tuple[str, int]:
    prefix = (prefix or "").upper()
    if prefix not in _NUMBER_SOURCES:
        raise ValueError(f"Unbekannter Nummernkreis-Prefix {prefix!r}. "
                         f"Erlaubt: {', '.join(_NUMBER_SOURCES)}.")
    table, col, where = _NUMBER_SOURCES[prefix]
    row = con.execute(
        f"SELECT MAX(CAST(SUBSTR({col}, 3) AS INTEGER)) FROM {table} WHERE {where}"
    ).fetchone()
    maxn = row[0] if row else None
    next_n = (maxn or 0) + 1
    return f"{prefix}-{next_n:05d}", next_n


def next_number(prefix: str) -> tuple[str, int]:
    con = _ro_conn()
    try:
        return _next_number_on(con, prefix)
    finally:
        con.close()


def _sync_number_sequence(con: sqlite3.Connection, prefix: str, next_after: int) -> None:
    con.execute("UPDATE number_sequences SET next_number = ? WHERE prefix = ?",
                (next_after, (prefix or "").upper()))


def _contact_type(contact_id: int) -> str | None:
    con = _ro_conn()
    try:
        row = con.execute("SELECT contact_type FROM contacts WHERE id = ?",
                          (contact_id,)).fetchone()
    finally:
        con.close()
    return row[0] if row else None


def _contact_address(contact_id: int):
    con = _ro_conn()
    try:
        return con.execute("SELECT strasse, plz, stadt FROM contacts WHERE id = ?",
                          (contact_id,)).fetchone()
    finally:
        con.close()


def _resolve_expense_category(code: str):
    con = _ro_conn()
    try:
        row = con.execute("SELECT id FROM expense_categories WHERE code = ?",
                          (code,)).fetchone()
    finally:
        con.close()
    return row[0] if row else None


def _conditions_text(template_id: int) -> tuple[str | None, int]:
    con = _ro_conn()
    try:
        row = con.execute(
            "SELECT text, payment_term_days FROM conditions_templates WHERE id = ?",
            (template_id,)).fetchone()
    finally:
        con.close()
    return (row[0], row[1]) if row else (None, 14)


def _last_quote_pattern() -> dict | None:
    con = _ro_conn()
    try:
        last = con.execute(
            "SELECT id, number FROM documents WHERE doc_type='quote' AND number LIKE 'A-%' "
            "ORDER BY CAST(SUBSTR(number, 3) AS INTEGER) DESC LIMIT 1").fetchone()
        if not last:
            return None
        doc_id, number = last
        rows = con.execute(
            "SELECT i.unit, i.billing_type FROM line_items i "
            "JOIN line_item_groups g ON i.group_id = g.id WHERE g.document_id = ?",
            (doc_id,)).fetchall()
    finally:
        con.close()
    return {"number": number,
            "units": {r[0] for r in rows},
            "billing_types": {r[1] for r in rows}}


def _num(value, field_name: str, errors: list[str], *, allow_zero: bool = True):
    try:
        n = float(value)
    except (TypeError, ValueError):
        errors.append(f"{field_name} '{value}' ist keine Zahl.")
        return None
    if n < 0:
        errors.append(f"{field_name} darf nicht negativ sein (war {n}).")
        return None
    if not allow_zero and n == 0:
        errors.append(f"{field_name} muss groesser 0 sein.")
        return None
    return n


def _check_date(value, field_name: str, errors: list[str]) -> str | None:
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except (TypeError, ValueError):
        errors.append(f"{field_name} '{value}' nicht im Format YYYY-MM-DD.")
        return None


def _insert_document(con, *, contact_id, doc_type, number, subject, status, date_,
                     valid_until, due_date, conditions_text, service_period,
                     payment_term_days, internal_notes, now) -> int:
    cur = con.execute(
        "INSERT INTO documents (contact_id, doc_type, number, subject, status, date, "
        "valid_until, due_date, conditions_text, service_period, payment_term_days, "
        "dunning_level, created_at, updated_at, internal_notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
        (contact_id, doc_type, number, subject, status, date_, valid_until, due_date,
         conditions_text, service_period, payment_term_days, now, now, internal_notes),
    )
    return cur.lastrowid


def _insert_group(con, doc_id, position, title, description, now) -> int:
    cur = con.execute(
        "INSERT INTO line_item_groups (document_id, position, title, description, "
        "created_at) VALUES (?, ?, ?, ?, ?)",
        (doc_id, position, title, description, now))
    return cur.lastrowid


def _insert_line_item(con, group_id, position, *, title, description, quantity, unit,
                      unit_price, vat_rate, billing_type) -> None:
    con.execute(
        "INSERT INTO line_items (group_id, position, title, description, quantity, unit, "
        "unit_price, vat_rate, billing_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (group_id, position, title, description, quantity, unit, unit_price,
         vat_rate, billing_type))


def _totals(items: list[dict]) -> dict:
    def s(field_, bt):
        return round(sum(field_(it) for it in items if it["billing_type"] == bt), 2)
    net_line = lambda it: it["quantity"] * it["unit_price"]
    vat_line = lambda it: it["quantity"] * it["unit_price"] * it["vat_rate"] / 100
    on_net, re_net = s(net_line, "onetime"), s(net_line, "recurring")
    on_vat, re_vat = s(vat_line, "onetime"), s(vat_line, "recurring")
    return {
        "onetime_net": on_net, "onetime_gross": round(on_net + on_vat, 2),
        "recurring_net": re_net, "recurring_gross": round(re_net + re_vat, 2),
    }


def _incoming_audit_trail(number: str, exemption: str, pdf_target: str | None) -> str:
    lines = [f"=== AUDIT-TRAIL {number} ===",
             f"Erfasst: {date.today().isoformat()} durch Max",
             f"Befreiung: {exemption}"]
    if pdf_target:
        lines.append(f"Beleg-PDF: {os.path.basename(pdf_target)}")
    lines.append("=== ENDE AUDIT-TRAIL ===")
    return "\n".join(lines)


def create_incoming_invoice(
    supplier_id: int,
    external_invoice_number: str,
    subject: str,
    net_amount,
    *,
    vat_rate=20,
    invoice_date: str | None = None,
    delivery_date: str | None = None,
    posting_date: str | None = None,
    due_date: str | None = None,
    payment_date: str | None = None,
    category_code: str | None = None,
    payment_method: str | None = None,
    vat_exemption_reason: str | None = None,
    is_vat_deductible: bool = True,
    gross_amount=None,
    pdf_source_path: str | None = None,
    internal_notes: str | None = None,
    commit: bool = False,
) -> WriteResult:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        supplier_id = int(supplier_id)
    except (TypeError, ValueError):
        return WriteResult(ok=False, committed=False,
                           errors=[f"supplier_id '{supplier_id}' ist keine Zahl."])

    ctype = _contact_type(supplier_id)
    if ctype is None:
        return WriteResult(ok=False, committed=False,
                           errors=[f"Lieferant (contact_id={supplier_id}) existiert nicht. "
                                   f"Keine Neuanlage im Schreibpfad — im Skill klaeren."])
    will_flip = ctype == "customer"
    if will_flip:
        warnings.append(f"Kontakt ist aktuell contact_type='customer' -> wird beim "
                        f"Commit auf 'both' gesetzt (Gate 2).")

    external_invoice_number = (external_invoice_number or "").strip()
    if not external_invoice_number:
        errors.append("Externe Rechnungsnummer ist Pflicht.")
    subject = (subject or "").strip()
    if not subject:
        errors.append("Betreff ist Pflicht.")

    net = _num(net_amount, "Netto", errors)
    rate = _num(vat_rate, "USt-Satz", errors)

    if rate == 0 and not (vat_exemption_reason or "").strip():
        errors.append("Gate 4: 0%-USt/Reverse-Charge braucht einen Befreiungsgrund "
                      "(z.B. 'Reverse Charge §19 UStG').")

    vat_amt = gross_computed = None
    if net is not None and rate is not None:
        vat_amt = round(net * rate / 100, 2)
        gross_computed = round(net + vat_amt, 2)
        if gross_amount is not None:
            ug = _num(gross_amount, "Brutto", errors)
            if ug is not None and abs(ug - gross_computed) > 0.01:
                errors.append(f"Gate 3: Brutto-Mismatch — erwartet {gross_computed:.2f}, "
                              f"uebergeben {ug:.2f} (Toleranz 0.01).")

    inv_date = invoice_date or date.today().isoformat()
    if invoice_date:
        _check_date(invoice_date, "Rechnungsdatum", errors)
    deliv = delivery_date or inv_date
    if delivery_date:
        _check_date(delivery_date, "Lieferdatum", errors)
    post = posting_date or inv_date
    if posting_date:
        _check_date(posting_date, "Buchungsdatum", errors)
    if due_date:
        _check_date(due_date, "Faelligkeitsdatum", errors)
    if payment_date:
        _check_date(payment_date, "Zahlungsdatum", errors)

    if pdf_source_path:
        if not os.path.isfile(pdf_source_path):
            errors.append(f"Gate 1/6: PDF-Pfad existiert nicht: {pdf_source_path}")
        else:
            try:
                import pdfplumber
                with pdfplumber.open(pdf_source_path) as pdf:
                    txt = (pdf.pages[0].extract_text() or "") if pdf.pages else ""
                if len(txt) < 50:
                    warnings.append("Gate 1: PDF liefert <50 Zeichen Text — evtl. Bild-Scan "
                                    "(OCR noetig). Mit Bestaetigung fortfahren.")
            except ImportError:
                warnings.append("pdfplumber nicht installiert — Gate 1 (Lesbarkeit) "
                                "uebersprungen.")
            except Exception as exc:
                warnings.append(f"Gate 1: PDF nicht lesbar ({exc}).")

    cat_id = None
    if category_code:
        cat_id = _resolve_expense_category(category_code)
        if cat_id is None:
            warnings.append(f"Kategorie-Code '{category_code}' nicht in expense_categories "
                            f"gefunden — expense_category_id bleibt NULL.")

    if external_invoice_number:
        con = _ro_conn()
        try:
            dup = con.execute(
                "SELECT number FROM incoming_invoices WHERE supplier_id = ? "
                "AND external_invoice_number = ?",
                (supplier_id, external_invoice_number)).fetchone()
        finally:
            con.close()
        if dup:
            errors.append(f"Beleg schon erfasst als {dup[0]} (gleiche Lieferant+Ext-Nr). "
                          f"UNIQUE-Constraint — Doppelerfassung verhindert.")

    if errors:
        return WriteResult(ok=False, committed=False, errors=errors, warnings=warnings)

    prospective, _ = next_number("E")
    kontakt = contact_label(supplier_id)
    status = "paid" if payment_date else "open"
    summary = "\n".join([
        f"Lieferant: {kontakt} (id={supplier_id})",
        f"  Beleg-Nr (vorauss.): {prospective} · Ext-Nr: {external_invoice_number}",
        f"  Betreff: {subject}",
        f"  Netto: {net:.2f} € · USt ({rate:.0f}%): {vat_amt:.2f} € · Brutto: {gross_computed:.2f} €",
        f"  Datum: {inv_date} · Buchung: {post} · Faellig: {due_date or '—'}",
        f"  Status: {status} · Vorsteuer: {'ja' if is_vat_deductible else 'nein'}",
        f"  Kategorie: {category_code or '—'}"
        + (f" (id={cat_id})" if cat_id else ""),
        f"  Befreiung: {vat_exemption_reason or '—'}",
        f"  PDF: {'ja' if pdf_source_path else 'nein'}",
    ])

    if not commit:
        return WriteResult(ok=True, committed=False, warnings=warnings,
                           summary="VORSCHAU Eingangsrechnung:\n" + summary)

    now = _now_sql()
    con = _rw_conn()
    try:
        number, next_n = _next_number_on(con, "E")
        pdf_target = f"{_incoming_pdf_dir()}/{number}.pdf" if pdf_source_path else None
        notes = internal_notes or ""
        if vat_exemption_reason and "AUDIT-TRAIL" not in notes.upper():
            block = _incoming_audit_trail(number, vat_exemption_reason, pdf_target)
            notes = (notes + "\n\n" + block).strip() if notes else block
        beleg_status = "vorhanden" if pdf_source_path else "fehlt"

        cur = con.execute(
            "INSERT INTO incoming_invoices "
            "(number, supplier_id, expense_category_id, external_invoice_number, subject, "
            "invoice_date, delivery_date, posting_date, due_date, payment_date, "
            "net_amount, vat_rate, vat_amount, gross_amount, vat_exemption_reason, "
            "is_vat_deductible, payment_method, document_file_path, beleg_status, status, "
            "internal_notes, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (number, supplier_id, cat_id, external_invoice_number, subject,
             inv_date, deliv, post, due_date, payment_date,
             net, rate, vat_amt, gross_computed, vat_exemption_reason,
             1 if is_vat_deductible else 0, payment_method, pdf_target, beleg_status,
             status, notes or None, now, now),
        )
        new_id = cur.lastrowid

        if will_flip:
            con.execute("UPDATE contacts SET contact_type = 'both', updated_at = ? "
                        "WHERE id = ?", (now, supplier_id))

        _sync_number_sequence(con, "E", next_n + 1)

        if pdf_source_path:
            os.makedirs(os.path.dirname(pdf_target), exist_ok=True)
            shutil.copy(pdf_source_path, pdf_target)
            if os.path.getsize(pdf_target) <= 0:
                raise ValueError("Abgelegtes PDF ist leer (Gate 6).")

        con.commit()
    except Exception as exc:
        con.rollback()
        return WriteResult(ok=False, committed=False, warnings=warnings,
                           errors=[f"Insert fehlgeschlagen (Rollback): {exc}"])
    finally:
        con.close()

    return WriteResult(ok=True, committed=True, row_id=new_id, warnings=warnings,
                       summary=f"Eingangsrechnung {number} erfasst (id={new_id}):\n{summary}")


def _normalize_positions(positions, errors, *, gate_quote_units: bool):
    norm: list[dict] = []
    if not positions:
        errors.append("Mindestens eine Position ist Pflicht.")
        return norm
    for i, p in enumerate(positions):
        path = f"Position {i + 1}"
        title = (p.get("title") or "").strip()
        if not title:
            errors.append(f"{path}: Titel ist Pflicht.")
        qty = _num(p.get("quantity", 1), f"{path}.quantity", errors, allow_zero=True)
        price = _num(p.get("unit_price", 0), f"{path}.unit_price", errors)
        rate = _num(p.get("vat_rate", 20), f"{path}.vat_rate", errors)
        unit = p.get("unit", "Pauschal")
        bt = p.get("billing_type", "onetime")
        if bt not in QUOTE_ALLOWED_BILLING_TYPES:
            errors.append(f"{path}.billing_type='{bt}' ungueltig "
                          f"(erlaubt: {', '.join(QUOTE_ALLOWED_BILLING_TYPES)}; "
                          f"Gate 2: 'hourly' verboten).")
        if gate_quote_units:
            if unit not in QUOTE_ALLOWED_UNITS:
                errors.append(f"{path}.unit='{unit}' ungueltig (Gate 3, erlaubt: "
                              f"{', '.join(QUOTE_ALLOWED_UNITS)}).")
            if unit == "Stunden" and bt != "onetime":
                errors.append(f"{path}: unit='Stunden' MUSS billing_type='onetime' "
                              f"sein (Gate 2 — 'hourly'/recurring fliesst nicht in "
                              f"total_onetime_net ein).")
        norm.append({
            "title": title, "description": p.get("description"),
            "quantity": qty if qty is not None else 1,
            "unit": unit, "unit_price": price if price is not None else 0,
            "vat_rate": rate if rate is not None else 20, "billing_type": bt,
        })
    return norm


def create_invoice(
    contact_id: int,
    subject: str,
    positions: list[dict],
    *,
    service_period: str | None = None,
    status: str = "draft",
    payment_term_days: int = 14,
    group_title: str | None = None,
    internal_notes: str | None = None,
    invoice_date: str | None = None,
    skip_umlaut_check: bool = False,
    commit: bool = False,
) -> WriteResult:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        contact_id = int(contact_id)
    except (TypeError, ValueError):
        return WriteResult(ok=False, committed=False,
                           errors=[f"contact_id '{contact_id}' ist keine Zahl."])
    if not contact_exists(contact_id):
        return WriteResult(ok=False, committed=False,
                           errors=[f"contact_id {contact_id} existiert nicht. "
                                   f"Keine Neuanlage im Rechnungs-Schreibpfad."])

    subject = (subject or "").strip()
    if not subject:
        errors.append("Betreff/Leistung ist Pflicht.")

    if status not in INVOICE_STATUS_KEYS:
        errors.append(f"status '{status}' ungueltig fuer Rechnung "
                      f"(erlaubt: {', '.join(INVOICE_STATUS_KEYS)}).")

    try:
        payment_term_days = int(payment_term_days)
        if payment_term_days < 0:
            errors.append("payment_term_days darf nicht negativ sein.")
    except (TypeError, ValueError):
        errors.append(f"payment_term_days '{payment_term_days}' ist keine Zahl.")
        payment_term_days = 14

    addr = _contact_address(contact_id)
    if addr:
        strasse, plz, stadt = addr
        missing = [n for n, v in (("strasse", strasse), ("plz", plz), ("stadt", stadt))
                   if not (v or "").strip()]
        if missing:
            errors.append(f"Adress-Gate (§11 UStG): {', '.join(missing)} fehlt am Kontakt "
                          f"{contact_id}. Im Skill aus belegter Quelle backfillen oder "
                          f"erfragen — NICHT raten.")

    if not service_period:
        warnings.append("Kein service_period gesetzt — bei laufenden/monatlichen "
                        "Leistungen ist der Leistungszeitraum Pflicht (§11 UStG). "
                        "Bei reiner Einmal-Leistung ohne Zeitbezug ok.")

    inv_date = invoice_date or date.today().isoformat()
    if invoice_date:
        _check_date(invoice_date, "Rechnungsdatum", errors)

    grp_title = (group_title or subject).strip()

    items = _normalize_positions(positions, errors, gate_quote_units=False)

    if not skip_umlaut_check:
        texts = [subject, grp_title, internal_notes, service_period]
        for it in items:
            texts += [it.get("title"), it.get("description")]
        for bad, good in check_umlauts(*texts):
            errors.append(f"Umlaut-Typo '{bad}' -> '{good}'. Korrigieren vor dem Anlegen.")

    if errors:
        return WriteResult(ok=False, committed=False, errors=errors, warnings=warnings)

    totals = _totals(items)
    prospective, _ = next_number("R")
    kontakt = contact_label(contact_id)
    due = (date.fromisoformat(inv_date) + timedelta(days=payment_term_days)).isoformat()
    summary = "\n".join([
        f"Empfaenger: {kontakt} (id={contact_id})",
        f"  Rechnungs-Nr (vorauss.): {prospective} · Datum: {inv_date} · faellig: {due}",
        f"  Betreff: {subject}",
        f"  Leistungszeitraum: {service_period or '— (geklaert?)'}",
        f"  Positionen: {len(items)} · Status: {status}",
        f"  Netto einmalig: {totals['onetime_net']:.2f} € "
        f"(Brutto {totals['onetime_gross']:.2f} €)",
        f"  Netto monatlich: {totals['recurring_net']:.2f} € "
        f"(Brutto {totals['recurring_gross']:.2f} €)",
    ])

    if not commit:
        return WriteResult(ok=True, committed=False, warnings=warnings,
                           summary="VORSCHAU Rechnung:\n" + summary)

    now = _now_sql()
    con = _rw_conn()
    try:
        number, next_n = _next_number_on(con, "R")
        due = (date.fromisoformat(inv_date) + timedelta(days=payment_term_days)).isoformat()
        doc_id = _insert_document(
            con, contact_id=contact_id, doc_type="invoice", number=number, subject=subject,
            status=status, date_=inv_date, valid_until=None, due_date=due,
            conditions_text=None, service_period=service_period,
            payment_term_days=payment_term_days, internal_notes=internal_notes, now=now)
        group_id = _insert_group(con, doc_id, 0, grp_title, None, now)
        for pos, it in enumerate(items):
            _insert_line_item(con, group_id, pos, title=it["title"],
                              description=it["description"], quantity=it["quantity"],
                              unit=it["unit"], unit_price=it["unit_price"],
                              vat_rate=it["vat_rate"], billing_type=it["billing_type"])
        _sync_number_sequence(con, "R", next_n + 1)
        con.commit()
    except Exception as exc:
        con.rollback()
        return WriteResult(ok=False, committed=False, warnings=warnings,
                           errors=[f"Insert fehlgeschlagen (Rollback): {exc}"])
    finally:
        con.close()

    return WriteResult(ok=True, committed=True, row_id=doc_id, warnings=warnings,
                       summary=f"Rechnung {number} angelegt (doc_id={doc_id}):\n{summary}")


def create_quote(
    contact_id: int,
    document: dict,
    groups: list[dict],
    *,
    skip_umlaut_check: bool = False,
    skip_pattern_check: bool = False,
    commit: bool = False,
) -> WriteResult:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        contact_id = int(contact_id)
    except (TypeError, ValueError):
        return WriteResult(ok=False, committed=False,
                           errors=[f"contact_id '{contact_id}' ist keine Zahl."])
    if not contact_exists(contact_id):
        return WriteResult(ok=False, committed=False,
                           errors=[f"contact_id {contact_id} existiert nicht (Gate 4: "
                                   f"Kontakt vorher im Skill aufloesen/anlegen)."])

    document = document or {}
    subject = (document.get("subject") or "").strip()
    if not subject:
        errors.append("document.subject ist Pflicht.")
    status = document.get("status", "draft")
    if status not in QUOTE_STATUS_KEYS:
        errors.append(f"status '{status}' ungueltig fuer Angebot "
                      f"(erlaubt: {', '.join(QUOTE_STATUS_KEYS)}).")
    elif status == "converted":
        errors.append("status 'converted' kann nicht beim Anlegen gesetzt werden "
                      "(entsteht nur beim Umwandeln in eine Rechnung).")

    flat_items: list[dict] = []
    if not groups:
        errors.append("Mindestens eine Gruppe mit Positionen ist Pflicht.")
    for gi, g in enumerate(groups or []):
        gitems = _normalize_positions(g.get("items", []), errors, gate_quote_units=True)
        flat_items += gitems

    if not skip_umlaut_check:
        texts = [subject, document.get("conditions_text_override"),
                 document.get("internal_notes")]
        for g in groups or []:
            texts += [g.get("title"), g.get("description")]
            for it in g.get("items", []):
                texts += [it.get("title"), it.get("description")]
        for bad, good in check_umlauts(*texts):
            errors.append(f"Umlaut-Typo '{bad}' -> '{good}'. Korrigieren "
                          f"(oder skip_umlaut_check nach Bestaetigung).")

    if not skip_pattern_check:
        last = _last_quote_pattern()
        if last:
            spec_units = {it["unit"] for it in flat_items}
            spec_bts = {it["billing_type"] for it in flat_items}
            novel_u = spec_units - last["units"]
            novel_b = spec_bts - last["billing_types"]
            if novel_u:
                warnings.append(f"Gate 7: neue Units ggue. {last['number']}: "
                                f"{sorted(novel_u)} (bisher {sorted(last['units'])}).")
            if novel_b:
                warnings.append(f"Gate 7: neue Billing-Types ggue. {last['number']}: "
                                f"{sorted(novel_b)} (bisher {sorted(last['billing_types'])}).")

    if errors:
        return WriteResult(ok=False, committed=False, errors=errors, warnings=warnings)

    totals = _totals(flat_items)
    prospective, _ = next_number("A")
    kontakt = contact_label(contact_id)
    valid_days = document.get("valid_until_days", 30)
    valid_until = (date.today() + timedelta(days=valid_days)).isoformat()
    summary = "\n".join([
        f"Empfaenger: {kontakt} (id={contact_id})",
        f"  Angebots-Nr (vorauss.): {prospective} · Status: {status} · gueltig bis {valid_until}",
        f"  Subject: {subject}",
        f"  Gruppen: {len(groups)} · Positionen: {len(flat_items)}",
        f"  Brutto einmalig: {totals['onetime_gross']:.2f} € "
        f"(netto {totals['onetime_net']:.2f})",
        f"  Brutto monatlich: {totals['recurring_gross']:.2f} € "
        f"(netto {totals['recurring_net']:.2f})",
    ])

    if not commit:
        return WriteResult(ok=True, committed=False, warnings=warnings,
                           summary="VORSCHAU Angebot:\n" + summary)

    now = _now_sql()
    template_id = document.get("conditions_template_id", 4)
    cond_default, term_default = _conditions_text(template_id)
    conditions_text = document.get("conditions_text_override") or cond_default
    payment_term_days = document.get("payment_term_days", term_default or 14)
    internal_notes = document.get("internal_notes")

    con = _rw_conn()
    try:
        number, next_n = _next_number_on(con, "A")
        doc_id = _insert_document(
            con, contact_id=contact_id, doc_type="quote", number=number, subject=subject,
            status=status, date_=date.today().isoformat(), valid_until=valid_until,
            due_date=None, conditions_text=conditions_text, service_period=None,
            payment_term_days=payment_term_days, internal_notes=internal_notes, now=now)
        for gpos, g in enumerate(groups):
            gtitle = (g.get("title") or "").strip()
            if g.get("optional") and "(optional)" not in gtitle.lower():
                gtitle = f"{gtitle} (optional)".strip()
            group_id = _insert_group(con, doc_id, gpos, gtitle, g.get("description"), now)
            for ipos, raw in enumerate(g.get("items", [])):
                quantity = raw.get("quantity", 1)
                if g.get("optional") and "quantity" not in raw:
                    quantity = 0
                _insert_line_item(
                    con, group_id, ipos, title=(raw.get("title") or "").strip(),
                    description=raw.get("description"), quantity=quantity,
                    unit=raw.get("unit", "Einmalig"), unit_price=raw.get("unit_price", 0),
                    vat_rate=raw.get("vat_rate", 20),
                    billing_type=raw.get("billing_type", "onetime"))
        _sync_number_sequence(con, "A", next_n + 1)
        con.commit()
    except Exception as exc:
        con.rollback()
        return WriteResult(ok=False, committed=False, warnings=warnings,
                           errors=[f"Insert fehlgeschlagen (Rollback): {exc}"])
    finally:
        con.close()

    return WriteResult(ok=True, committed=True, row_id=doc_id, warnings=warnings,
                       summary=f"Angebot {number} angelegt (doc_id={doc_id}):\n{summary}")



DEAD_LEAD_STATUSES = ("lost", "closed_no_response", "bounced")

_BELEG_SUBQUERY = (
    "SELECT contact_id FROM documents WHERE contact_id IS NOT NULL "
    "UNION SELECT contact_id FROM time_entries WHERE contact_id IS NOT NULL "
    "UNION SELECT contact_id FROM tasks WHERE contact_id IS NOT NULL "
    "UNION SELECT supplier_id FROM incoming_invoices WHERE supplier_id IS NOT NULL "
    "UNION SELECT contact_id FROM retainers WHERE contact_id IS NOT NULL"
)

ARCHIVE_SCOPES = {
    "dead": "status IN ('lost','closed_no_response','bounced')",
    "dead_plus_dormant": (
        "(status IN ('lost','closed_no_response','bounced') "
        "OR (status = 'new' AND kontaktiert IS NULL))"
    ),
    "dead_plus_dormant_keep_a": (
        "(status IN ('lost','closed_no_response','bounced') "
        "OR (status = 'new' AND kontaktiert IS NULL AND COALESCE(lead_score, 0) < 40))"
    ),
    "dead_plus_weak_new": (
        "(status IN ('lost','closed_no_response','bounced') "
        "OR (status = 'new' AND COALESCE(lead_score, 0) < 25))"
    ),
}
DEFAULT_ARCHIVE_SCOPE = "dead_plus_dormant_keep_a"


def _archive_where(scope: str) -> str:
    cohort = ARCHIVE_SCOPES[scope]
    return (
        "(abrechnungsmodell IS NULL OR abrechnungsmodell = '') "
        "AND erinnerung IS NULL "
        "AND (archived = 0 OR archived IS NULL) "
        f"AND id NOT IN ({_BELEG_SUBQUERY}) "
        f"AND {cohort}"
    )


def find_contacts(search: str, *, include_archived: bool = False,
                  limit: int = 50) -> list[dict]:
    term = f"%{(search or '').strip()}%"
    sql = ("SELECT id, organisation, hourly_rate, abrechnungsmodell, archived "
           "FROM contacts WHERE organisation LIKE ?")
    if not include_archived:
        sql += " AND (archived = 0 OR archived IS NULL)"
    sql += " ORDER BY organisation LIMIT ?"
    con = _ro_conn()
    try:
        rows = con.execute(sql, (term, limit)).fetchall()
    finally:
        con.close()
    return [dict(id=r[0], organisation=r[1], hourly_rate=r[2],
                 abrechnungsmodell=r[3], archived=bool(r[4])) for r in rows]


def set_archived(contact_id: int, archived: bool, *,
                 commit: bool = False) -> WriteResult:
    try:
        contact_id = int(contact_id)
    except (TypeError, ValueError):
        return WriteResult(ok=False, committed=False,
                           errors=[f"Ungueltige contact_id: {contact_id!r}"])
    label = contact_label(contact_id)
    if label is None:
        return WriteResult(ok=False, committed=False, row_id=contact_id,
                           errors=[f"Kontakt {contact_id} existiert nicht."])
    target = 1 if archived else 0
    verb = "archivieren" if archived else "reaktivieren"
    summary = f"Kontakt {contact_id} ({label}) -> {verb}"
    if not commit:
        return WriteResult(ok=True, committed=False, row_id=contact_id,
                           summary="VORSCHAU:\n  " + summary)
    con = _rw_conn()
    try:
        cur = con.execute(
            "UPDATE contacts SET archived = ?, updated_at = ? WHERE id = ?",
            (target, _now(), contact_id))
        if cur.rowcount != 1:
            con.rollback()
            return WriteResult(ok=False, committed=False, row_id=contact_id,
                               errors=[f"Erwartete 1 Zeile, {cur.rowcount} betroffen — Rollback."])
        con.commit()
    finally:
        con.close()
    return WriteResult(ok=True, committed=True, row_id=contact_id, summary=summary)


def archive_stale_leads(*, scope: str = DEFAULT_ARCHIVE_SCOPE,
                        commit: bool = False) -> WriteResult:
    if scope not in ARCHIVE_SCOPES:
        return WriteResult(ok=False, committed=False,
                           errors=[f"Unbekannter scope '{scope}'. "
                                   f"Erlaubt: {', '.join(ARCHIVE_SCOPES)}."])
    where = _archive_where(scope)
    con = _ro_conn()
    try:
        count = con.execute(
            f"SELECT COUNT(*) FROM contacts WHERE {where}").fetchone()[0]
        sample = con.execute(
            f"SELECT id, organisation, status, lead_score FROM contacts "
            f"WHERE {where} ORDER BY lead_score DESC, id LIMIT 10").fetchall()
    finally:
        con.close()

    meta = {"scope": scope, "count": count,
            "sample": [dict(id=r[0], organisation=r[1], status=r[2], lead_score=r[3])
                       for r in sample]}
    head = f"Bulk-Archivierung scope='{scope}': {count} Kontakte betroffen."

    if count == 0:
        return WriteResult(ok=True, committed=False, meta=meta,
                           summary=head + " Nichts zu tun.")

    if not commit:
        lines = [f"    #{r[0]} {r[1]} [{r[2]}, score {r[3]}]" for r in sample]
        tail = "\n    ..." if count > len(sample) else ""
        return WriteResult(ok=True, committed=False, meta=meta,
                           summary="VORSCHAU (kein Write):\n  " + head
                                   + "\n" + "\n".join(lines) + tail)

    con = _rw_conn()
    try:
        cur = con.execute(
            f"UPDATE contacts SET archived = 1, updated_at = ? WHERE {where}",
            (_now(),))
        affected = cur.rowcount
        con.commit()
    finally:
        con.close()
    meta["archived"] = affected
    return WriteResult(ok=True, committed=True, meta=meta,
                       summary=f"{affected} Kontakte archiviert (scope='{scope}').")


def _as_iso_date(value, field_name: str, errors: list[str]) -> str | None:
    if value is None:
        errors.append(f"{field_name} ist Pflicht.")
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        errors.append(f"{field_name} '{text}' nicht im Format YYYY-MM-DD.")
        return None


def import_bank_transactions(
    rows: list[dict],
    filename: str,
    *,
    schema_name: str | None = None,
    commit: bool = False,
) -> WriteResult:
    errors: list[str] = []
    warnings: list[str] = []

    filename = (filename or "").strip()
    if not filename:
        errors.append("filename ist Pflicht (Audit-Trail des Imports).")
    if not rows:
        errors.append("Keine Zeilen zum Importieren.")
    if errors:
        return WriteResult(ok=False, committed=False, errors=errors)

    prepared: list[dict] = []
    for idx, row in enumerate(rows, start=1):
        row_errors: list[str] = []
        booking = _as_iso_date(row.get("booking_date"), f"Zeile {idx}: booking_date", row_errors)
        value_date = row.get("value_date")
        value_iso = None
        if value_date is not None:
            throwaway: list[str] = []
            value_iso = _as_iso_date(value_date, "value_date", throwaway)
        amount = row.get("amount")
        if amount is None:
            row_errors.append(f"Zeile {idx}: amount fehlt.")
        row_hash = (row.get("row_hash") or "").strip()
        if not row_hash:
            row_errors.append(f"Zeile {idx}: row_hash fehlt — ohne ihn keine Idempotenz.")
        if row_errors:
            errors.extend(row_errors)
            continue
        fc = (row.get("foreign_currency") or "").upper()[:3] or None
        fa = row.get("foreign_amount")
        prepared.append({
            "booking_date": booking,
            "value_date": value_iso,
            "amount": float(amount),
            "currency": (row.get("currency") or "EUR").upper()[:3],
            "foreign_currency": fc if fc and fc != "EUR" else None,
            "foreign_amount": float(fa) if (fa is not None and fc and fc != "EUR") else None,
            "partner_name": row.get("partner_name"),
            "partner_iban": row.get("partner_iban"),
            "reference": row.get("reference"),
            "tx_type": row.get("tx_type"),
            "row_hash": row_hash,
        })

    if errors:
        return WriteResult(ok=False, committed=False, errors=errors)

    dates = sorted(r["booking_date"] for r in prepared)
    period_from, period_to = dates[0], dates[-1]

    con = _ro_conn()
    try:
        known = {
            r[0] for r in con.execute(
                "SELECT row_hash FROM bank_transactions WHERE row_hash IN "
                f"({','.join('?' * len(prepared))})",
                [r["row_hash"] for r in prepared],
            )
        }
    finally:
        con.close()

    fresh = [r for r in prepared if r["row_hash"] not in known]
    duplicates = len(prepared) - len(fresh)
    if duplicates:
        warnings.append(f"{duplicates} von {len(prepared)} Zeilen liegen bereits in der DB "
                        f"und werden uebersprungen.")
    if not fresh:
        warnings.append("Keine neue Zeile in dieser Datei — vermutlich derselbe Export "
                        "wie zuvor.")

    summary = (f"Bank-Import '{filename}' ({schema_name or 'Schema unbekannt'})\n"
               f"  Zeitraum: {period_from} bis {period_to}\n"
               f"  {len(prepared)} Zeilen gelesen · {len(fresh)} neu · "
               f"{duplicates} Duplikate")
    meta = {"row_count": len(prepared), "new": len(fresh), "duplicates": duplicates,
            "period_from": period_from, "period_to": period_to,
            "schema_name": schema_name}

    if not commit:
        return WriteResult(ok=True, committed=False, meta=meta,
                           warnings=warnings, summary="VORSCHAU " + summary)

    con = _rw_conn()
    try:
        now = _now_sql()
        cur = con.execute(
            "INSERT INTO bank_imports (filename, schema_name, imported_at, row_count, "
            "new_count, duplicate_count, period_from, period_to) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (filename, schema_name, now, len(prepared), 0, duplicates,
             period_from, period_to),
        )
        import_id = cur.lastrowid

        inserted = 0
        for row in fresh:
            res = con.execute(
                "INSERT INTO bank_transactions ("
                "  import_id, booking_date, value_date, amount, currency,"
                "  foreign_amount, foreign_currency,"
                "  partner_name, partner_iban, reference, tx_type, row_hash,"
                "  match_status, created_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unmatched', ?) "
                "ON CONFLICT(row_hash) DO NOTHING",
                (import_id, row["booking_date"], row["value_date"], row["amount"],
                 row["currency"], row["foreign_amount"], row["foreign_currency"],
                 row["partner_name"], row["partner_iban"],
                 row["reference"], row["tx_type"], row["row_hash"], now),
            )
            inserted += res.rowcount or 0

        raced = len(fresh) - inserted
        con.execute(
            "UPDATE bank_imports SET new_count = ?, duplicate_count = ? WHERE id = ?",
            (inserted, duplicates + raced, import_id),
        )
        con.commit()
    finally:
        con.close()

    if raced:
        warnings.append(f"{raced} Zeilen wurden waehrend des Imports von einem "
                        f"parallelen Lauf angelegt.")
    meta.update({"import_id": import_id, "new": inserted,
                 "duplicates": duplicates + raced})
    return WriteResult(ok=True, committed=True, row_id=import_id, meta=meta,
                       warnings=warnings,
                       summary=f"Import #{import_id} angelegt:\n{summary}")


def _fetch_bank_transaction(con: sqlite3.Connection, tx_id: int):
    return con.execute(
        "SELECT id, booking_date, amount, reference, match_status, "
        "       matched_document_id, matched_incoming_invoice_id "
        "FROM bank_transactions WHERE id = ?",
        (tx_id,),
    ).fetchone()


def confirm_bank_match(
    tx_id: int,
    *,
    document_id: int | None = None,
    incoming_invoice_id: int | None = None,
    note: str | None = None,
    commit: bool = False,
) -> WriteResult:
    errors: list[str] = []

    try:
        tx_id = int(tx_id)
    except (TypeError, ValueError):
        return WriteResult(ok=False, committed=False,
                           errors=[f"tx_id '{tx_id}' ist keine Zahl."])

    if (document_id is None) == (incoming_invoice_id is None):
        return WriteResult(ok=False, committed=False, errors=[
            "Genau eines von document_id / incoming_invoice_id ist zu setzen "
            "(entweder Ausgangs- ODER Eingangsrechnung)."])

    con = _ro_conn()
    try:
        tx = _fetch_bank_transaction(con, tx_id)
        if tx is None:
            return WriteResult(ok=False, committed=False,
                               errors=[f"bank_transaction {tx_id} existiert nicht."])
        _, booking_date, amount, reference, match_status, mdoc, minc = tx

        if match_status == "confirmed":
            existing = mdoc or minc
            return WriteResult(ok=False, committed=False, errors=[
                f"bank_transaction {tx_id} ist bereits bestaetigt "
                f"(Beleg-Verweis {existing}). Keine stille Doppelbuchung."])

        amount = float(amount or 0)
        if document_id is not None and amount < 0:
            errors.append("Abbuchung (negativer Betrag) kann keine Ausgangsrechnung "
                          "bezahlen.")
        if incoming_invoice_id is not None and amount > 0:
            errors.append("Zahlungseingang (positiver Betrag) gehoert nicht auf eine "
                          "Eingangsrechnung.")
        if errors:
            return WriteResult(ok=False, committed=False, errors=errors)

        if document_id is not None:
            beleg = con.execute(
                "SELECT number, status, doc_type, payment_date FROM documents WHERE id = ?",
                (document_id,),
            ).fetchone()
            if beleg is None:
                return WriteResult(ok=False, committed=False,
                                   errors=[f"document {document_id} existiert nicht."])
            number, status, doc_type, _ = beleg
            if doc_type != "invoice":
                errors.append(f"{number} ist kein invoice (doc_type='{doc_type}') "
                              f"und kann nicht bezahlt werden.")
            if status not in INVOICE_PAID_FROM_STATUSES:
                errors.append(
                    f"{number} steht auf '{status}'. Auf 'paid' darf nur aus "
                    f"{list(INVOICE_PAID_FROM_STATUSES)} gewechselt werden.")
            target_label = number
        else:
            beleg = con.execute(
                "SELECT number, status FROM incoming_invoices WHERE id = ?",
                (incoming_invoice_id,),
            ).fetchone()
            if beleg is None:
                return WriteResult(ok=False, committed=False, errors=[
                    f"incoming_invoice {incoming_invoice_id} existiert nicht."])
            number, status = beleg
            if status == "paid":
                errors.append(f"{number} ist bereits als bezahlt gebucht.")
            target_label = number
    finally:
        con.close()

    if errors:
        return WriteResult(ok=False, committed=False, errors=errors)

    summary = (f"{target_label} auf 'paid' + Zahldatum {booking_date}\n"
               f"  Bank-Zeile #{tx_id}: {amount:.2f} EUR · "
               f"{(reference or '(kein Verwendungszweck)')[:60]}")
    meta = {"target": target_label, "payment_date": booking_date, "amount": amount}

    if not commit:
        return WriteResult(ok=True, committed=False, meta=meta,
                           summary="VORSCHAU Bank-Match:\n" + summary)

    con = _rw_conn()
    try:
        now = _now_sql()
        if document_id is not None:
            placeholders = ",".join("?" * len(INVOICE_PAID_FROM_STATUSES))
            cur = con.execute(
                f"UPDATE documents SET status = 'paid', payment_date = ?, updated_at = ? "
                f"WHERE id = ? AND status IN ({placeholders})",
                (booking_date, now, document_id, *INVOICE_PAID_FROM_STATUSES),
            )
            if cur.rowcount == 0:
                con.rollback()
                return WriteResult(ok=False, committed=False, errors=[
                    f"{target_label} hat waehrend der Bestaetigung den Status "
                    f"gewechselt. Nichts geschrieben, bitte neu laden."])
            con.execute(
                "INSERT INTO document_status_log (document_id, from_status, to_status, "
                "changed_at, note) VALUES (?, ?, 'paid', ?, ?)",
                (document_id, status, now,
                 note or f"Bank-Abgleich: Zeile #{tx_id}, Zahldatum {booking_date}"),
            )
            con.execute(
                "UPDATE bank_transactions SET match_status = 'confirmed', "
                "matched_document_id = ?, confirmed_at = ?, note = ? WHERE id = ?",
                (document_id, now, note, tx_id),
            )
        else:
            cur = con.execute(
                "UPDATE incoming_invoices SET status = 'paid', payment_date = ?, "
                "updated_at = ? WHERE id = ? AND status != 'paid'",
                (booking_date, now, incoming_invoice_id),
            )
            if cur.rowcount == 0:
                con.rollback()
                return WriteResult(ok=False, committed=False, errors=[
                    f"{target_label} wurde zwischenzeitlich bezahlt gebucht. "
                    f"Nichts geschrieben."])
            con.execute(
                "UPDATE bank_transactions SET match_status = 'confirmed', "
                "matched_incoming_invoice_id = ?, confirmed_at = ?, note = ? WHERE id = ?",
                (incoming_invoice_id, now, note, tx_id),
            )
        con.commit()
    finally:
        con.close()

    return WriteResult(ok=True, committed=True, row_id=tx_id, meta=meta,
                       summary=f"Bank-Match bestaetigt: {summary}")


def correct_payment_date(
    document_id: int,
    new_date,
    *,
    note: str | None = None,
    commit: bool = False,
) -> WriteResult:
    errors: list[str] = []

    try:
        document_id = int(document_id)
    except (TypeError, ValueError):
        return WriteResult(ok=False, committed=False,
                           errors=[f"document_id '{document_id}' ist keine Zahl."])

    iso_new = _as_iso_date(new_date, "new_date", errors)
    if errors:
        return WriteResult(ok=False, committed=False, errors=errors)

    con = _ro_conn()
    try:
        row = con.execute(
            "SELECT number, doc_type, status, date, payment_date, source_document_id "
            "FROM documents WHERE id = ?", (document_id,)).fetchone()
        if row is None:
            return WriteResult(ok=False, committed=False,
                               errors=[f"document {document_id} existiert nicht."])
        number, doc_type, status, doc_date, old_date, source_id = row

        untergrenze, grenz_beleg = doc_date, "Rechnungsdatum"
        if source_id:
            src = con.execute(
                "SELECT number, date FROM documents WHERE id = ?", (source_id,)).fetchone()
            if src and src[1] and str(src[1]) < str(doc_date or ""):
                untergrenze = src[1]
                grenz_beleg = f"Rechnungsdatum des Originals {src[0]}"
    finally:
        con.close()

    if doc_type != "invoice":
        errors.append(f"{number} ist kein invoice (doc_type='{doc_type}').")
    if status != "paid":
        errors.append(f"{number} steht auf '{status}'. Ein Zahldatum korrigiert man "
                      f"nur an einer bezahlten Rechnung.")
    if iso_new > date.today().isoformat():
        errors.append(f"Zahldatum {iso_new} liegt in der Zukunft.")
    if untergrenze and iso_new < str(untergrenze):
        errors.append(f"Zahldatum {iso_new} liegt vor dem {grenz_beleg} {untergrenze}.")
    if errors:
        return WriteResult(ok=False, committed=False, errors=errors)

    if str(old_date or "") == iso_new:
        return WriteResult(ok=True, committed=False, meta={"skipped": True},
                           summary=f"SKIP {number}: Zahldatum ist bereits {iso_new}.")

    monatswechsel = (str(old_date or "")[:7] != iso_new[:7])
    summary = (f"{number}: Zahldatum {old_date} -> {iso_new}"
               + ("  [MONATSWECHSEL]" if monatswechsel else ""))
    meta = {"number": number, "old": str(old_date or ""), "new": iso_new,
            "monatswechsel": monatswechsel, "skipped": False}

    if not commit:
        return WriteResult(ok=True, committed=False, meta=meta,
                           summary="VORSCHAU " + summary)

    con = _rw_conn()
    try:
        cur = con.execute(
            "UPDATE documents SET payment_date = ?, updated_at = ? "
            "WHERE id = ? AND status = 'paid'",
            (iso_new, _now_sql(), document_id))
        if cur.rowcount == 0:
            con.rollback()
            return WriteResult(ok=False, committed=False, errors=[
                f"{number} hat waehrend der Korrektur den Status gewechselt. "
                f"Nichts geschrieben."])
        con.execute(
            "INSERT INTO document_status_log (document_id, from_status, to_status, "
            "changed_at, note) VALUES (?, 'paid', 'paid', ?, ?)",
            (document_id, _now_sql(),
             note or f"Zahldatum korrigiert: {old_date} -> {iso_new}"))
        con.commit()
    finally:
        con.close()

    return WriteResult(ok=True, committed=True, row_id=document_id, meta=meta,
                       summary=summary)


def ignore_bank_transaction(tx_id: int, *, note: str | None = None,
                            commit: bool = False) -> WriteResult:
    try:
        tx_id = int(tx_id)
    except (TypeError, ValueError):
        return WriteResult(ok=False, committed=False,
                           errors=[f"tx_id '{tx_id}' ist keine Zahl."])

    con = _ro_conn()
    try:
        tx = _fetch_bank_transaction(con, tx_id)
    finally:
        con.close()
    if tx is None:
        return WriteResult(ok=False, committed=False,
                           errors=[f"bank_transaction {tx_id} existiert nicht."])
    if tx[4] == "confirmed":
        return WriteResult(ok=False, committed=False, errors=[
            f"bank_transaction {tx_id} ist bestaetigt und einem Beleg zugeordnet — "
            f"sie kann nicht auf 'ignored' gesetzt werden."])

    summary = f"Bank-Zeile #{tx_id} ({float(tx[2] or 0):.2f} EUR) braucht keinen Beleg"
    if not commit:
        return WriteResult(ok=True, committed=False, summary="VORSCHAU " + summary)

    con = _rw_conn()
    try:
        con.execute(
            "UPDATE bank_transactions SET match_status = 'ignored', note = ? WHERE id = ?",
            (note, tx_id))
        con.commit()
    finally:
        con.close()
    return WriteResult(ok=True, committed=True, row_id=tx_id, summary=summary)


if __name__ == "__main__":
    print("=== close_task preview (erster offener Task) ===")
    con = _ro_conn()
    row = con.execute(
        "SELECT id FROM tasks WHERE status IN ('todo','in_arbeit','backlog') "
        "ORDER BY id LIMIT 1"
    ).fetchone()
    con.close()
    if row:
        print(close_task(row[0], commit=False).report())

    print("\n=== create_task preview (valide) ===")
    print(create_task("Rauchtest — nur Vorschau", priority="hoch",
                       due_date="2026-08-01", commit=False).report())

    print("\n=== create_time_entry preview (bad contact) ===")
    print(create_time_entry(999999, 30, "Testnotiz", "beratung", commit=False).report())

    print("\n=== next_number previews (R/A/E/K/H) ===")
    for pfx in ("R", "A", "E", "K", "H"):
        try:
            print(f"  {pfx}: {next_number(pfx)[0]}")
        except Exception as exc:
            print(f"  {pfx}: FEHLER {exc}")
    print("\nPreview-Rauchtest fertig (kein Write ausgefuehrt).")
