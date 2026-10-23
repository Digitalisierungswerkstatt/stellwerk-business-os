import os
import sqlite3
import sys
from email.header import Header
from email.message import EmailMessage
from email import message_from_string

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import email_import as ei

EIGENE = {"office@musterwerkstatt.example"}


def _sent_with_signature_and_quote():
    return message_from_string(
        "Message-ID: <abc123@mail.host>\r\n"
        "Date: Mon, 20 Jul 2026 09:00:00 +0200\r\n"
        "From: Max Mustermann <office@musterwerkstatt.example>\r\n"
        "To: Max Muster <max@kunde.at>\r\n"
        "Subject: Angebot Website-Relaunch\r\n"
        "Content-Type: text/plain; charset=\"utf-8\"\r\n"
        "\r\n"
        "Hallo Max,\r\n"
        "anbei wie besprochen das Angebot.\r\n"
        "\r\n"
        "-- \r\n"
        "Max Mustermann | Musterwerkstatt\r\n"
        "\r\n"
        "Am 19.07.2026 schrieb Max Muster:\r\n"
        "> das ist die alte Nachricht\r\n"
    )


def _received_umlaut_qp():
    subj = Header("Anfrage für Projekt", "utf-8").encode()
    return message_from_string(
        "Message-ID: <recv77@mail.host>\r\n"
        "Date: Tue, 21 Jul 2026 10:30:00 +0200\r\n"
        "From: \"Kundin Extern\" <kundin@extern.at>\r\n"
        "To: office@musterwerkstatt.example\r\n"
        f"Subject: {subj}\r\n"
        "Content-Type: text/plain; charset=\"utf-8\"\r\n"
        "Content-Transfer-Encoding: quoted-printable\r\n"
        "\r\n"
        "Gr=C3=BC=C3=9Fe und Fragen zum Projekt.\r\n"
    )


def _html_only():
    return message_from_string(
        "Message-ID: <html1@mail.host>\r\n"
        "Date: Wed, 22 Jul 2026 08:00:00 +0200\r\n"
        "From: web@extern.at\r\n"
        "To: office@musterwerkstatt.example\r\n"
        "Subject: HTML\r\n"
        "Content-Type: text/html; charset=\"utf-8\"\r\n"
        "\r\n"
        "<html><body><p>Hallo,</p><p>hier der <b>wichtige</b> Text.</p>"
        "<script>ignore()</script></body></html>\r\n"
    )


def test_parse_headers_and_date():
    p = ei.parse_mail(_sent_with_signature_and_quote())
    assert p.message_id == "<abc123@mail.host>"
    assert p.datum == "2026-07-20"
    assert p.betreff == "Angebot Website-Relaunch"
    assert p.from_addr == "office@musterwerkstatt.example"
    assert p.to_addrs == ["max@kunde.at"]


def test_parse_preview_cuts_signature_and_quote():
    p = ei.parse_mail(_sent_with_signature_and_quote())
    assert p.preview == "Hallo Max, anbei wie besprochen das Angebot."
    assert "alte Nachricht" not in p.preview
    assert "Musterwerkstatt" not in p.preview


def test_parse_rfc2047_subject_and_quoted_printable_body():
    p = ei.parse_mail(_received_umlaut_qp())
    assert p.betreff == "Anfrage für Projekt"
    assert "Grüße und Fragen zum Projekt." in p.preview


def test_parse_preview_cuts_forward_banner_with_note():
    msg = message_from_string(
        "Message-ID: <fwd1@mail.host>\r\n"
        "Date: Fri, 28 Nov 2025 10:00:00 +0100\r\n"
        "From: office@musterwerkstatt.example\r\nTo: office@partneragentur.example\r\n"
        "Subject: Fwd: Info\r\nContent-Type: text/plain; charset=\"utf-8\"\r\n\r\n"
        "Schau dir das an.\r\n\r\n"
        "-------- Weitergeleitete Nachricht --------\r\n"
        "Betreff: Beginninformation\r\nDatum: Fri, 28 Nov 2025 09:00:00 +0100\r\n"
    )
    assert ei.parse_mail(msg).preview == "Schau dir das an."


def test_parse_preview_leading_forward_banner_is_empty():
    msg = message_from_string(
        "Message-ID: <fwd2@mail.host>\r\n"
        "From: office@musterwerkstatt.example\r\nTo: office@partneragentur.example\r\n"
        "Subject: Fwd: Info\r\nContent-Type: text/plain; charset=\"utf-8\"\r\n\r\n"
        "-------- Weitergeleitete Nachricht --------\r\n"
        "Betreff: X\r\n"
    )
    assert ei.parse_mail(msg).preview == ""


def test_parse_html_only_stripped():
    p = ei.parse_mail(_html_only())
    assert "Hallo" in p.preview and "wichtige" in p.preview and "Text" in p.preview
    assert "<" not in p.preview and "ignore" not in p.preview


def test_parse_from_bytes():
    raw = _sent_with_signature_and_quote().as_bytes()
    p = ei.parse_mail(raw)
    assert p.message_id == "<abc123@mail.host>"


def test_parse_missing_message_id_surrogate():
    msg = message_from_string(
        "Date: Mon, 20 Jul 2026 09:00:00 +0200\r\n"
        "From: x@extern.at\r\n"
        "To: office@musterwerkstatt.example\r\n"
        "Subject: Ohne ID\r\n\r\nBody.\r\n"
    )
    p = ei.parse_mail(msg)
    assert p.message_id.startswith("<no-msgid:")
    assert ei.parse_mail(msg).message_id == p.message_id


def test_parse_preview_truncation():
    long = "A" * 500
    msg = message_from_string(
        "Message-ID: <long@mail.host>\r\n"
        "From: x@extern.at\r\nTo: office@musterwerkstatt.example\r\n"
        "Subject: L\r\nContent-Type: text/plain; charset=\"utf-8\"\r\n\r\n" + long
    )
    p = ei.parse_mail(msg)
    assert len(p.preview) <= ei.PREVIEW_LIMIT + 1
    assert p.preview.endswith("…")


def test_parse_unparseable_date_is_none():
    msg = message_from_string(
        "Message-ID: <baddate@mail.host>\r\n"
        "Date: total kaputt\r\nFrom: x@extern.at\r\n"
        "To: office@musterwerkstatt.example\r\nSubject: X\r\n\r\nBody.\r\n"
    )
    assert ei.parse_mail(msg).datum is None


def test_counterparties_sent_direction_from_own_from():
    p = ei.parse_mail(_sent_with_signature_and_quote())
    cps = ei.extract_counterparties(p, EIGENE)
    assert cps == [("Gesendet", "max@kunde.at")]


def test_counterparties_received_direction():
    p = ei.parse_mail(_received_umlaut_qp())
    cps = ei.extract_counterparties(p, EIGENE)
    assert cps == [("Empfangen", "kundin@extern.at")]


def test_counterparties_sent_multi_recipient_excludes_own():
    msg = EmailMessage()
    msg["Message-ID"] = "<multi@mail.host>"
    msg["Date"] = "Mon, 20 Jul 2026 09:00:00 +0200"
    msg["From"] = "office@musterwerkstatt.example"
    msg["To"] = "a@kunde.at, b@kunde.at"
    msg["Cc"] = "office@musterwerkstatt.example, c@kunde.at"
    msg["Subject"] = "Rundmail"
    msg.set_content("Text an mehrere.")
    p = ei.parse_mail(msg)
    cps = ei.extract_counterparties(p, EIGENE)
    gegen = [a for _, a in cps]
    assert set(gegen) == {"a@kunde.at", "b@kunde.at", "c@kunde.at"}
    assert all(r == "Gesendet" for r, _ in cps)
    assert "office@musterwerkstatt.example" not in gegen


def test_counterparties_empty_when_no_from():
    msg = message_from_string(
        "Message-ID: <nofrom@mail.host>\r\nDate: Mon, 20 Jul 2026 09:00:00 +0200\r\n"
        "To: office@musterwerkstatt.example\r\nSubject: X\r\n\r\nBody.\r\n"
    )
    assert ei.extract_counterparties(ei.parse_mail(msg), EIGENE) == []


def _contacts_db():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE contacts (id INTEGER PRIMARY KEY, "
                "mail_organisation TEXT, mail_person TEXT, mail_rechnung TEXT)")
    con.executemany(
        "INSERT INTO contacts (id, mail_organisation, mail_person, mail_rechnung) "
        "VALUES (?, ?, ?, ?)",
        [
            (1, "info@kunde.at", "max@kunde.at", None),
            (2, "Office@Firma.AT", None, "buchhaltung@firma.at"),
            (3, "shared@x.at", None, None),
            (4, "shared@x.at", None, None),
        ],
    )
    return con


def test_match_person_column_lowercase():
    con = _contacts_db()
    assert ei.match_contacts(con, "MAX@KUNDE.AT") == [1]


def test_match_rechnung_column():
    con = _contacts_db()
    assert ei.match_contacts(con, "buchhaltung@firma.at") == [2]


def test_match_organisation_case_insensitive_stored():
    con = _contacts_db()
    assert ei.match_contacts(con, "office@firma.at") == [2]


def test_match_no_hit_returns_empty():
    con = _contacts_db()
    assert ei.match_contacts(con, "niemand@nirgends.at") == []


def test_match_multiple_contacts_same_address():
    con = _contacts_db()
    assert sorted(ei.match_contacts(con, "shared@x.at")) == [3, 4]


def test_match_empty_address():
    con = _contacts_db()
    assert ei.match_contacts(con, "") == []
