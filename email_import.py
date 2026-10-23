
from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from email.header import decode_header, make_header
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime
from html import unescape

EIGENE_ADRESSEN_DEFAULT = {
    "office@musterwerkstatt.example",
    "hallo@beispielverein.example",
    "google@beispielverein.example",
}

PREVIEW_LIMIT = 200

_CUT_MARKERS = [
    re.compile(r"\n-- \n"),
    re.compile(r"\nAm .{0,120}? schrieb.{0,60}?:", re.S),
    re.compile(r"\nOn .{0,120}? wrote:", re.S),
    re.compile(r"\nVon:\s"),
    re.compile(r"\n_{5,}"),
    re.compile(r"(?:^|\n)-{2,}\s*(Weitergeleitete Nachricht|Urspr[uü]ngliche Nachricht|"
               r"Original Message|Forwarded message)", re.I),
]


@dataclass
class ParsedMail:
    message_id: str
    datum: str | None
    betreff: str
    from_addr: str
    to_addrs: list[str] = field(default_factory=list)
    cc_addrs: list[str] = field(default_factory=list)
    preview: str = ""


def _decode_hdr(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return value.strip()


def _addrs(msg: Message, header: str) -> list[str]:
    raw = msg.get_all(header, [])
    out: list[str] = []
    seen: set[str] = set()
    for _name, addr in getaddresses(raw):
        a = (addr or "").strip().lower()
        if a and "@" in a and a not in seen:
            seen.add(a)
            out.append(a)
    return out


def _first_addr(msg: Message, header: str) -> str:
    a = _addrs(msg, header)
    return a[0] if a else ""


def _message_id(msg: Message) -> str:
    mid = (msg.get("Message-ID") or "").strip()
    if mid:
        return mid
    basis = "|".join([msg.get("From", "") or "", msg.get("Date", "") or "",
                      msg.get("Subject", "") or ""])
    h = hashlib.sha1(basis.encode("utf-8", "replace")).hexdigest()[:16]
    return f"<no-msgid:{h}>"


def _mail_date(msg: Message) -> str | None:
    raw = msg.get("Date")
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        return dt.date().isoformat() if dt else None
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def _decode_payload(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, TypeError):
        return payload.decode("utf-8", errors="replace")


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</(p|div|tr|li|h[1-6])>", "\n", html)
    html = re.sub(r"<[^>]+>", " ", html)
    return unescape(html)


def _body_text(msg: Message) -> str:
    plain = html = None
    if msg.is_multipart():
        for part in msg.walk():
            if part.is_multipart():
                continue
            disp = str(part.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                continue
            ctype = part.get_content_type()
            if ctype == "text/plain" and plain is None:
                plain = _decode_payload(part)
            elif ctype == "text/html" and html is None:
                html = _decode_payload(part)
    else:
        if msg.get_content_type() == "text/html":
            html = _decode_payload(msg)
        else:
            plain = _decode_payload(msg)
    if plain and plain.strip():
        return plain
    if html and html.strip():
        return _html_to_text(html)
    return ""


def _clean_preview(text: str, limit: int = PREVIEW_LIMIT) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    cut = len(text)
    for rx in _CUT_MARKERS:
        m = rx.search(text)
        if m:
            cut = min(cut, m.start())
    text = text[:cut]
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith(">")]
    text = re.sub(r"\s+", " ", " ".join(lines)).strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text


def parse_mail(raw: bytes | Message) -> ParsedMail:
    if isinstance(raw, (bytes, bytearray)):
        import email as _email
        msg = _email.message_from_bytes(bytes(raw))
    else:
        msg = raw
    return ParsedMail(
        message_id=_message_id(msg),
        datum=_mail_date(msg),
        betreff=_decode_hdr(msg.get("Subject")),
        from_addr=_first_addr(msg, "From"),
        to_addrs=_addrs(msg, "To"),
        cc_addrs=_addrs(msg, "Cc"),
        preview=_clean_preview(_body_text(msg)),
    )


def extract_counterparties(parsed: ParsedMail,
                           eigene_adressen: set[str]) -> list[tuple[str, str]]:
    eigene = {a.lower() for a in eigene_adressen}
    frm = parsed.from_addr
    if frm and frm in eigene:
        gegen = [a for a in (parsed.to_addrs + parsed.cc_addrs) if a not in eigene]
        seen: set[str] = set()
        uniq = [a for a in gegen if not (a in seen or seen.add(a))]
        return [("Gesendet", a) for a in uniq]
    if frm and frm not in eigene:
        return [("Empfangen", frm)]
    return []


def match_contacts(con: sqlite3.Connection, adresse: str) -> list[int]:
    a = (adresse or "").strip().lower()
    if not a:
        return []
    rows = con.execute(
        "SELECT id FROM contacts WHERE "
        "lower(mail_organisation) = ? OR lower(mail_person) = ? OR lower(mail_rechnung) = ?",
        (a, a, a),
    ).fetchall()
    return [r[0] for r in rows]


_SKIP_FOLDER_FLAGS = ("\\Junk", "\\Trash", "\\Drafts", "\\Noselect")
_IMAP_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _imap_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day:02d}-{_IMAP_MONTHS[d.month - 1]}-{d.year}"


def _folder_flags_name(raw: bytes) -> tuple[str, str]:
    d = raw.decode()
    flags = d[d.find("(") + 1:d.find(")")]
    tail = d[d.find(")") + 1:].strip()
    parts = tail.split(" ", 1)
    name = parts[1].strip() if len(parts) > 1 else ""
    if name.startswith('"') and name.endswith('"'):
        name = name[1:-1]
    return flags, name


def _mbox_arg(name: str) -> str:
    if re.match(r"^[A-Za-z0-9/_.-]+$", name):
        return name
    return '"' + name.replace('"', '\\"') + '"'


def _scan_folders(imap) -> list[str]:
    typ, folders = imap.list()
    names: list[str] = []
    for raw in folders or []:
        flags, name = _folder_flags_name(raw)
        if any(fl in flags for fl in _SKIP_FOLDER_FLAGS):
            continue
        if name:
            names.append(name)
    return names


def fetch_mails(imap, since: str | None, until: str | None):
    search_args = ("ALL",)
    if since:
        search_args = ("SINCE", _imap_date(since))
    for folder in _scan_folders(imap):
        try:
            typ, _ = imap.select(_mbox_arg(folder), readonly=True)
            if typ != "OK":
                continue
            typ, data = imap.search(None, *search_args)
            if typ != "OK" or not data or not data[0]:
                continue
            for num in data[0].split():
                typ, md = imap.fetch(num, "(BODY.PEEK[])")
                if typ != "OK" or not md or not md[0]:
                    continue
                yield folder, md[0][1]
        except Exception as exc:
            print(f"  ! Ordner '{folder}' uebersprungen: {exc}")
            continue


def run_import(since, until, commit, eigene, db_path, sample=0):
    from collections import Counter
    import stellwerk_write as sw

    match_con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    match_con.execute("PRAGMA busy_timeout=5000")

    scanned = matched_mails = no_match = written = deduped = would_new = 0
    per_contact = Counter()
    samples: list[tuple[str, str]] = []
    seen_keys: set[tuple[int, str]] = set()

    import os as _os
    IMAP_SERVER = _os.getenv("EMAIL_IMAP_SERVER")
    IMAP_PORT = int(_os.getenv("EMAIL_IMAP_PORT", 993))
    EMAIL_ADDRESS = _os.getenv("EMAIL_ADDRESS")
    EMAIL_PASSWORD = _os.getenv("EMAIL_PASSWORD")

    import imaplib
    imap = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    imap.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    try:
        for folder, raw in fetch_mails(imap, since, until):
            scanned += 1
            parsed = parse_mail(raw)
            if until and parsed.datum and parsed.datum > until:
                continue
            cps = extract_counterparties(parsed, eigene)
            hit_this_mail = False
            for richtung, adr in cps:
                for cid in match_contacts(match_con, adr):
                    key = (cid, parsed.message_id)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    hit_this_mail = True
                    per_contact[cid] += 1
                    res = sw.create_interaction(
                        cid, parsed.datum, parsed.betreff, parsed.preview,
                        richtung, adr, parsed.message_id, commit=commit)
                    if res.committed:
                        written += 1
                    elif res.meta.get("skipped"):
                        deduped += 1
                    elif res.ok:
                        would_new += 1
                        if len(samples) < sample and res.meta.get("notiz"):
                            samples.append((sw.contact_label(cid) or f"contact {cid}",
                                            res.meta["notiz"]))
            if hit_this_mail:
                matched_mails += 1
            else:
                no_match += 1
    finally:
        imap.logout()
        match_con.close()

    print("=" * 64)
    print(f"Postfach: {EMAIL_ADDRESS}  |  seit: {since or 'Anfang'}"
          + (f"  bis: {until}" if until else ""))
    print(f"Gescannt:            {scanned} Mails")
    print(f"Mit Kontakt-Match:   {matched_mails} Mails -> {len(per_contact)} Kontakte")
    print(f"Ohne Kontakt (skip): {no_match} Mails")
    if commit:
        print(f"Geschrieben:         {written}  |  bereits importiert (dedup): {deduped}")
    else:
        print(f"Neu (wuerde schreiben): {would_new}  |  bereits importiert (dedup): {deduped}")
    if per_contact:
        print("--- Top-Kontakte ---")
        for cid, n in per_contact.most_common(15):
            label = sw.contact_label(cid) or f"contact {cid}"
            print(f"  {label} ({cid}): {n} Mails")
    if samples:
        print("\n--- Stichprobe: so wuerde die notiz aussehen ---")
        for i, (label, notiz) in enumerate(samples, 1):
            print(f"\n[{i}] {label}")
            for line in notiz.splitlines():
                print(f"    {line}")
    if not commit:
        print("\nTROCKENLAUF — 0 Zeilen geschrieben. Mit --commit ausfuehren.")
    print("=" * 64)
    return {"scanned": scanned, "matched_mails": matched_mails, "no_match": no_match,
            "written": written, "deduped": deduped, "would_new": would_new,
            "contacts": len(per_contact)}


def _load_env():
    import os as _os
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path.home() / ".env")
    missing = [k for k in ("EMAIL_IMAP_SERVER", "EMAIL_ADDRESS", "EMAIL_PASSWORD")
               if not _os.getenv(k)]
    return missing


if __name__ == "__main__":
    import argparse
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.path.insert(0, __import__("os").path.dirname(__file__))

    parser = argparse.ArgumentParser(
        description="Read-only-Import von Kundenmails als CRM-interactions.")
    parser.add_argument("--since", help="Nur Mails ab Datum (YYYY-MM-DD), IMAP SINCE")
    parser.add_argument("--until", help="Nur Mails bis Datum (YYYY-MM-DD), clientseitig")
    parser.add_argument("--commit", action="store_true",
                        help="Schreibt in die DB (Default: Trockenlauf/Preview)")
    parser.add_argument("--sample", type=int, default=0, metavar="N",
                        help="Zeigt N generierte notiz-Beispiele (nur Preview)")
    args = parser.parse_args()

    for d in (args.since, args.until):
        if d:
            try:
                date.fromisoformat(d)
            except ValueError:
                parser.error(f"Datum '{d}' nicht im Format YYYY-MM-DD.")

    missing = _load_env()
    if missing:
        print(f"FEHLER: {', '.join(missing)} fehlt in ~/.env — Abbruch (kein Hardcoding).")
        sys.exit(1)

    import os as _os
    import stellwerk_write as _sw
    eigene = set(EIGENE_ADRESSEN_DEFAULT)
    if _os.getenv("EMAIL_ADDRESS"):
        eigene.add(_os.getenv("EMAIL_ADDRESS").lower())

    if args.commit:
        print("!!! COMMIT-MODUS — schreibt interactions in die Produktiv-DB.")
    run_import(args.since, args.until, args.commit, eigene, _sw._db_path(),
               sample=args.sample)
