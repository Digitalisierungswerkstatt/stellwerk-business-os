
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stellwerk_write as sw
from mcp.server.mcpserver import MCPServer

server = MCPServer(
    name="stellwerk",
    version="1.0.0",
    instructions=(
        "Stellwerk ist das CRM und Task-Board der Musterwerkstatt. "
        "Alle schreibenden Werkzeuge sind zweistufig: ohne commit=True liefern sie "
        "nur eine Vorschau und beruehren die Datenbank nicht. Erst die Vorschau "
        "lesen, dann mit commit=True erneut aufrufen. "
        "Vor dem Weiterarbeiten an einem fremden Task gilt die Prämissen-Regel: "
        "ein Task-Status ist bei mehreren parallelen Sitzungen ein Zeitstempel, kein "
        "Zustand. Erst den Ist-Zustand messen, dann der Beschreibung glauben."
    ),
)


@server.tool()
def task_get(task_id: int) -> str:
    """Liest einen Stellwerk-Task samt Kommentaren, Kunde und Alter (read-only).

    Das Alter ist kein Beiwerk: je aelter ein Task, desto wahrscheinlicher ist
    seine Beschreibung von der Wirklichkeit ueberholt. Die Kommentare tragen
    haeufig den juengeren Stand als das Beschreibungsfeld.
    """
    try:
        task_id = int(task_id)
    except (TypeError, ValueError):
        return f"FEHLER: Ungueltige Task-ID: {task_id!r}"

    con = sw._ro_conn()
    try:
        row = con.execute(
            "SELECT id, title, description, status, priority, effort, impact, score, "
            "category, due_date, contact_id, created_by, created_at, updated_at, "
            "completed_at, recurrence_days FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            return f"Task #{task_id} existiert nicht."
        comments = con.execute(
            "SELECT author, content, created_at FROM task_comments "
            "WHERE task_id = ? ORDER BY created_at",
            (task_id,),
        ).fetchall()
    finally:
        con.close()

    (tid, title, description, status, priority, effort, impact, score, category,
     due_date, contact_id, created_by, created_at, updated_at, completed_at,
     recurrence_days) = row

    lines = [f"Task #{tid}: {title}",
             f"  Status: {status}   Prioritaet: {priority}"]
    if effort or impact or score is not None:
        lines.append(f"  Aufwand: {effort or '-'}   Wirkung: {impact or '-'}   Score: {score if score is not None else '-'}")
    if category:
        lines.append(f"  Kategorie: {category}")
    if due_date:
        lines.append(f"  Faellig: {due_date}{_overdue_marker(due_date, status)}")
    if recurrence_days:
        lines.append(f"  Wiederkehr: {sw.recurrence_label(recurrence_days)}")

    label = sw.contact_label(contact_id) if contact_id else None
    lines.append(f"  Kunde: {label} (contact_id={contact_id})" if label
                 else "  Kunde: — (kein Kontakt verknuepft)")

    lines.append(f"  Angelegt: {created_at} von {created_by}")
    lines.append(f"  Zuletzt geaendert: {updated_at}{_age_marker(updated_at)}")
    if completed_at:
        lines.append(f"  Abgeschlossen: {completed_at}")

    lines.append("")
    lines.append("BESCHREIBUNG:")
    lines.append(description.strip() if description and description.strip()
                 else "  (leer — die Beschreibung traegt hier keine Spec)")

    lines.append("")
    if comments:
        lines.append(f"KOMMENTARE ({len(comments)}, aeltester zuerst):")
        for author, content, ts in comments:
            lines.append(f"  [{ts}] {author}:")
            for cl in content.strip().splitlines():
                lines.append(f"      {cl}")
    else:
        lines.append("KOMMENTARE: keine")

    lines.append("")
    lines.append("MERKE: Dieser Datensatz sagt, was jemand einmal aufgeschrieben hat. "
                 "Ob es heute noch stimmt, sagt nur eine Messung am Zielsystem.")
    return "\n".join(lines)


def _age_marker(updated_at: str | None) -> str:
    if not updated_at:
        return ""
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            then = datetime.strptime(str(updated_at)[:26], fmt)
            break
        except ValueError:
            continue
    else:
        return ""
    days = (datetime.now() - then).days
    if days <= 0:
        return "   (heute)"
    if days == 1:
        return "   (1 Tag alt)"
    return f"   ({days} Tage alt — Beschreibung gegen den Ist-Zustand pruefen)"


def _overdue_marker(due_date: str | None, status: str | None) -> str:
    if not due_date or status in getattr(sw, "CLOSED_STATUSES", ()):
        return ""
    try:
        d = date.fromisoformat(str(due_date)[:10])
    except ValueError:
        return ""
    overdue = (date.today() - d).days
    return f"   (ueberfaellig seit {overdue} Tagen)" if overdue > 0 else ""


@server.tool()
def task_create(
    title: str,
    description: str | None = None,
    priority: str = "mittel",
    status: str = "todo",
    due_date: str | None = None,
    contact_id: int | None = None,
    category: str | None = None,
    created_by: str = "Max",
    commit: bool = False,
) -> str:
    """Legt einen Stellwerk-Task an. Ohne commit=True nur Vorschau, kein Write.

    Umlaute echt schreiben: ASCII-Ersatz ("fuer", "Aenderung", "bestaetigt")
    blockt hart, im Titel wie in der Beschreibung.
    """
    res = sw.create_task(
        title,
        description=description,
        priority=priority,
        status=status,
        due_date=due_date,
        contact_id=contact_id,
        category=category,
        created_by=created_by,
        commit=commit,
    )
    return _render(res, commit, f"task_create(title={title!r}, ..., commit=True)")


@server.tool()
def task_close(task_id: int, commit: bool = False) -> str:
    """Setzt einen Task auf 'erledigt'. Ohne commit=True nur Vorschau, kein Write.

    Idempotent: ein bereits geschlossener Task wird nicht erneut geschrieben.
    Traegt der Task eine Wiederkehr, entsteht beim Schliessen der Folge-Task.
    """
    res = sw.close_task(task_id, commit=commit)
    return _render(res, commit, f"task_close(task_id={task_id}, commit=True)")


@server.tool()
def task_comment(task_id: int, content: str, author: str = "Claude",
                 commit: bool = False) -> str:
    """Haengt einen Kommentar an einen Task. Ohne commit=True nur Vorschau.

    Der richtige Ort fuer einen Messbefund — besonders fuer den Beleg, dass die
    Prämisse eines Tasks widerlegt wurde.
    """
    res = sw.create_task_comment(task_id, content, author=author, commit=commit)
    return _render(res, commit, f"task_comment(task_id={task_id}, ..., commit=True)")


@server.tool()
def task_check(task_id: int, punkt: str, commit: bool = False) -> str:
    """Hakt genau eine Checkbox `- [ ] <punkt>…` in der Task-Beschreibung ab.
    Ohne commit=True nur Vorschau (Zeile vorher/nachher), kein Write.

    `punkt` ist der Anfang des Checkbox-Texts, z.B. "0.3" oder "B4". Kein oder
    mehrdeutiger Treffer bricht ab. Nach erledigter Arbeit: erst task_comment mit
    dem Beleg, dann task_check, damit Kommentar und Checkliste dasselbe sagen.
    """
    res = sw.check_task_item(task_id, punkt, commit=commit)
    return _render(res, commit, f"task_check(task_id={task_id}, punkt={punkt!r}, commit=True)")


@server.tool()
def time_book(
    contact_id: int,
    dauer_minuten: int,
    notiz: str,
    taetigkeit: str,
    datum: str | None = None,
    commit: bool = False,
) -> str:
    """Bucht Zeit auf einen Kontakt. Ohne commit=True nur Vorschau, kein Write.

    `taetigkeit` ist ein Enum aus models.py — der Lint nennt die gueltigen Werte,
    wenn der uebergebene nicht passt. `datum` leer = heute (ISO: YYYY-MM-DD).
    """
    res = sw.create_time_entry(
        contact_id,
        dauer_minuten,
        notiz,
        taetigkeit,
        datum=datum,
        commit=commit,
    )
    return _render(res, commit, f"time_book(contact_id={contact_id}, ..., commit=True)")


def _render(res, commit: bool, redo_hint: str) -> str:
    out = res.report() or "(keine Rueckmeldung)"
    if res.errors:
        return "NICHT GESCHRIEBEN — Eingabe abgelehnt:\n" + out
    if not commit:
        return (out + "\n\nNICHTS GESCHRIEBEN. Das war eine Vorschau. "
                f"Zum Ausfuehren erneut aufrufen mit: {redo_hint}")
    if not res.committed:
        return "NICHT GESCHRIEBEN:\n" + out
    return "GESCHRIEBEN:\n" + out


def _selftest() -> int:
    print(f"DB-Pfad: {sw._db_path()}")
    con = sw._ro_conn()
    try:
        offen = con.execute(
            "SELECT COUNT(*) FROM tasks WHERE status NOT IN ('erledigt', 'verworfen')"
        ).fetchone()[0]
        neuester = con.execute("SELECT MAX(id) FROM tasks").fetchone()[0]
    finally:
        con.close()
    print(f"Offene Tasks: {offen}   hoechste Task-ID: {neuester}")
    print("Werkzeuge: task_get, task_create, task_close, task_comment, task_check, time_book")
    if neuester:
        print("-" * 70)
        print(task_get(neuester))
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    server.run("stdio")
