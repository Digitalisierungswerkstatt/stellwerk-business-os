import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app as flask_app
from models import db, Contact, Task, Document, WikiPage, WikiEntry
import search_fts as sf


@pytest.fixture
def app():
    flask_app.config["TESTING"] = True
    yield flask_app


def test_fts5_available_in_shipped_sqlite():
    import sqlite3
    con = sqlite3.connect(":memory:")
    con.execute("CREATE VIRTUAL TABLE t USING fts5(a)")
    con.close()


def test_empty_query_returns_all_empty(app):
    result = sf.search_all("")
    assert result == {t: [] for t in sf.RESULT_TYPES}


def test_search_snippet_contains_markers(app):
    with app.app_context():
        c = Contact(organisation="SnippetMarker Testfirma")
        db.session.add(c)
        db.session.commit()
        cid = c.id

    hits = sf.search_all("SnippetMarker")["contacts"]
    assert any(h["id"] == cid for h in hits)
    hit = next(h for h in hits if h["id"] == cid)
    assert sf.SNIPPET_START in hit["snippet"]
    assert sf.SNIPPET_END in hit["snippet"]


def test_contact_found_by_organisation(app):
    with app.app_context():
        c = Contact(organisation="Alpenquell Vertrieb GmbH")
        db.session.add(c)
        db.session.commit()
        cid = c.id
    ids = [h["id"] for h in sf.search_all("Alpenquell")["contacts"]]
    assert cid in ids


def test_contact_found_by_email(app):
    with app.app_context():
        c = Contact(organisation="MailTest KG", mail_person="findme-unique@example.at")
        db.session.add(c)
        db.session.commit()
        cid = c.id
    ids = [h["id"] for h in sf.search_all("findme-unique")["contacts"]]
    assert cid in ids


def test_contact_found_by_kommentare(app):
    with app.app_context():
        c = Contact(organisation="NotizTest OG", kommentare="Braucht dringend ein neues CRM-Setup")
        db.session.add(c)
        db.session.commit()
        cid = c.id
    ids = [h["id"] for h in sf.search_all("CRM-Setup")["contacts"]]
    assert cid in ids


def test_archived_contact_excluded_by_default(app):
    with app.app_context():
        c = Contact(organisation="ArchivFirma Sonderfall", archived=True)
        db.session.add(c)
        db.session.commit()
        cid = c.id

    default_ids = [h["id"] for h in sf.search_all("ArchivFirma")["contacts"]]
    assert cid not in default_ids

    included_ids = [h["id"] for h in sf.search_all("ArchivFirma", include_archived=True)["contacts"]]
    assert cid in included_ids


def test_task_found_by_title(app):
    with app.app_context():
        t = Task(title="Suchtest-Task Onboarding pruefen", status="todo")
        db.session.add(t)
        db.session.commit()
        tid = t.id
    ids = [h["id"] for h in sf.search_all("Onboarding pruefen")["tasks"]]
    assert tid in ids


def test_document_found_by_number_and_subject(app):
    with app.app_context():
        c = Contact(organisation="DocSearch Kunde")
        db.session.add(c)
        db.session.flush()
        d = Document(contact_id=c.id, doc_type="quote", number="A-SEARCHTEST",
                     subject="Suchtest Praesentationskonzept", date=date(2026, 7, 1))
        db.session.add(d)
        db.session.commit()
        did = d.id
    ids_by_number = [h["id"] for h in sf.search_all("A-SEARCHTEST")["documents"]]
    assert did in ids_by_number
    ids_by_subject = [h["id"] for h in sf.search_all("Praesentationskonzept")["documents"]]
    assert did in ids_by_subject


def test_wiki_page_found_by_title_and_content(app):
    with app.app_context():
        wp = WikiPage(title="Suchtest Wiki-Seite", slug=WikiPage.slugify("Suchtest Wiki-Seite Unique"),
                       content="Enthaelt einen einzigartigen Rumpelstilzchen-Begriff")
        db.session.add(wp)
        db.session.commit()
        wpid = wp.id
    ids_title = [h["id"] for h in sf.search_all("Suchtest Wiki-Seite")["wiki_pages"]]
    assert wpid in ids_title
    ids_content = [h["id"] for h in sf.search_all("Rumpelstilzchen")["wiki_pages"]]
    assert wpid in ids_content


def test_wiki_entry_found_by_trigger_phrases(app):
    with app.app_context():
        we = WikiEntry(name="Suchtest Skill", slug=WikiPage.slugify("Suchtest Skill Unique"),
                        entry_type="skill", description="Testbeschreibung",
                        trigger_phrases="Zauberwort Bimborium aktivieren")
        db.session.add(we)
        db.session.commit()
        weid = we.id
    ids = [h["id"] for h in sf.search_all("Bimborium")["wiki_entries"]]
    assert weid in ids


def test_index_updates_after_orm_update(app):
    with app.app_context():
        c = Contact(organisation="VorherName Sync-Test")
        db.session.add(c)
        db.session.commit()
        cid = c.id

    assert cid in [h["id"] for h in sf.search_all("VorherName")["contacts"]]

    with app.app_context():
        c = Contact.query.get(cid)
        c.organisation = "NachherName Sync-Test"
        db.session.commit()

    assert cid not in [h["id"] for h in sf.search_all("VorherName")["contacts"]]
    assert cid in [h["id"] for h in sf.search_all("NachherName")["contacts"]]


def test_index_removes_entry_after_orm_delete(app):
    with app.app_context():
        c = Contact(organisation="LoeschTest Sync-Firma")
        db.session.add(c)
        db.session.commit()
        cid = c.id

    assert cid in [h["id"] for h in sf.search_all("LoeschTest")["contacts"]]

    with app.app_context():
        c = Contact.query.get(cid)
        db.session.delete(c)
        db.session.commit()

    assert cid not in [h["id"] for h in sf.search_all("LoeschTest")["contacts"]]
