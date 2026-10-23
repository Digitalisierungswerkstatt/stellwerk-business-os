import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app as flask_app
from models import db, ContentCalendarEntry, CONTENT_PLATFORMS
import content_publisher as cp

STORY_PLATFORM = 'instagram_story'
DW_CONTACT = 315


@pytest.fixture
def app():
    flask_app.config['TESTING'] = True
    yield flask_app


@pytest.fixture
def bild(tmp_path):
    p = tmp_path / 'story-1080x1920.png'
    p.write_bytes(b'nicht-wirklich-ein-png')
    return p


@pytest.fixture
def meta_publish_da(monkeypatch, tmp_path):
    fake = tmp_path / 'meta_publish.py'
    fake.write_text('# Attrappe', encoding='utf-8')
    monkeypatch.setattr(cp, 'META_PUBLISH', fake)
    return fake


@pytest.fixture
def aufgezeichnet(monkeypatch):
    calls = []

    class FakeProc:
        returncode = 0
        stderr = ''
        stdout = ''

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        proc = FakeProc()
        proc.stdout = fake_run.stdout
        return proc

    fake_run.stdout = ''
    monkeypatch.setattr(cp.subprocess, 'run', fake_run)
    return calls, fake_run


def _entry(platform, bild, text='Caption mit Umlauten: Gruesse aus Oberoesterreich',
           bilder=None):
    return ContentCalendarEntry(
        platform=platform, title='TEST_CP Eintrag', status='scheduled',
        contact_id=DW_CONTACT, content_text=text,
        asset_link=bilder if bilder is not None else str(bild),
    )



def test_story_ist_eine_content_platform():
    assert STORY_PLATFORM in {p[0] for p in CONTENT_PLATFORMS}


def test_story_laeuft_ueber_instagram_als_target():
    for platform in cp.STORY_PLATFORMS:
        assert cp.META_TARGETS.get(platform) == 'ig'


def test_story_eintrag_wird_vom_validator_akzeptiert(app):
    with app.app_context():
        entry = ContentCalendarEntry(platform=STORY_PLATFORM, title='x', status='scheduled')
        assert entry.platform == STORY_PLATFORM



def test_story_braucht_keine_caption(app, bild, meta_publish_da):
    with app.app_context():
        entry = _entry(STORY_PLATFORM, bild, text='')
        assert cp.check_entry(entry) is None


def test_feed_post_braucht_weiterhin_eine_caption(app, bild, meta_publish_da):
    with app.app_context():
        entry = _entry('instagram', bild, text='   ')
        reason = cp.check_entry(entry)
        assert reason is not None
        assert 'content_text' in reason


def test_story_mit_zwei_bildern_wird_abgelehnt(app, bild, meta_publish_da, tmp_path):
    zweites = tmp_path / 'story-2.png'
    zweites.write_bytes(b'x')
    with app.app_context():
        entry = _entry(STORY_PLATFORM, bild, bilder=f"{bild};{zweites.name}")
        reason = cp.check_entry(entry)
        assert reason is not None
        assert 'genau EIN Bild' in reason


def test_story_ohne_asset_wird_abgelehnt(app, meta_publish_da):
    with app.app_context():
        entry = _entry(STORY_PLATFORM, None, text='', bilder='')
        reason = cp.check_entry(entry)
        assert reason is not None
        assert 'asset_link' in reason


def test_karussell_mit_elf_bildern_bleibt_abgelehnt(app, bild, meta_publish_da, tmp_path):
    namen = []
    for i in range(11):
        p = tmp_path / f'slide{i}.png'
        p.write_bytes(b'x')
        namen.append(p.name if i else str(p))
    with app.app_context():
        entry = _entry('instagram', bild, bilder=';'.join(namen))
        reason = cp.check_entry(entry)
        assert reason is not None
        assert 'maximal 10' in reason



def test_story_kommandozeile_hat_story_und_keine_caption(app, bild, meta_publish_da, aufgezeichnet):
    calls, _ = aufgezeichnet
    with app.app_context():
        ok, message = cp.publish_entry(_entry(STORY_PLATFORM, bild), dry_run=True)
    assert ok, message
    assert len(calls) == 1
    cmd = calls[0]
    assert '--story' in cmd
    assert '--caption-file' not in cmd
    assert cmd[cmd.index('--target') + 1] == 'ig'
    assert cmd.count('--image') == 1
    assert '--publish' not in cmd


def test_feed_kommandozeile_hat_caption_und_kein_story(app, bild, meta_publish_da, aufgezeichnet):
    calls, _ = aufgezeichnet
    with app.app_context():
        ok, message = cp.publish_entry(_entry('instagram', bild), dry_run=True)
    assert ok, message
    cmd = calls[0]
    assert '--story' not in cmd
    assert '--caption-file' in cmd


def test_publish_flag_nur_ohne_dry_run(app, bild, meta_publish_da, aufgezeichnet):
    calls, _ = aufgezeichnet
    with app.app_context():
        cp.publish_entry(_entry(STORY_PLATFORM, bild), dry_run=False)
    assert '--publish' in calls[0]


def test_story_meldung_traegt_die_media_id(app, bild, meta_publish_da, aufgezeichnet):
    calls, fake_run = aufgezeichnet
    fake_run.stdout = ('  Instagram : STORY VEROEFFENTLICHT (media 17900000000000001)\n'
                       '  Naechster Schritt (nur in der App moeglich): Highlight.\n')
    with app.app_context():
        ok, message = cp.publish_entry(_entry(STORY_PLATFORM, bild), dry_run=False)
    assert ok
    assert '17900000000000001' in message
    assert 'App' in message


def test_returncode_ungleich_null_ist_kein_erfolg(app, bild, meta_publish_da, monkeypatch):
    class FailProc:
        returncode = 1
        stdout = 'irgendwas ging schief'
        stderr = ''

    monkeypatch.setattr(cp.subprocess, 'run', lambda cmd, **kw: FailProc())
    with app.app_context():
        ok, message = cp.publish_entry(_entry(STORY_PLATFORM, bild), dry_run=True)
    assert ok is False
    assert 'fehlgeschlagen' in message



def test_due_entries_nimmt_story_eintraege_auf(app):
    with app.app_context():
        faellig = ContentCalendarEntry(
            platform=STORY_PLATFORM, title='TEST_CP faellige Story', status='scheduled',
            scheduled_for=datetime.now() - timedelta(hours=1))
        spaeter = ContentCalendarEntry(
            platform=STORY_PLATFORM, title='TEST_CP kuenftige Story', status='scheduled',
            scheduled_for=datetime.now() + timedelta(days=3))
        entwurf = ContentCalendarEntry(
            platform=STORY_PLATFORM, title='TEST_CP nicht freigegeben', status='visual_fertig',
            scheduled_for=datetime.now() - timedelta(hours=1))
        db.session.add_all([faellig, spaeter, entwurf])
        db.session.commit()
        ids = [faellig.id, spaeter.id, entwurf.id]
        try:
            titel = [e.title for e in cp.due_entries()]
            assert 'TEST_CP faellige Story' in titel
            assert 'TEST_CP kuenftige Story' not in titel
            assert 'TEST_CP nicht freigegeben' not in titel
        finally:
            ContentCalendarEntry.query.filter(ContentCalendarEntry.id.in_(ids)).delete(
                synchronize_session=False)
            db.session.commit()


def test_gepostete_story_wird_nicht_erneut_faellig(app):
    with app.app_context():
        entry = ContentCalendarEntry(
            platform=STORY_PLATFORM, title='TEST_CP schon gepostet', status='scheduled',
            scheduled_for=datetime.now() - timedelta(hours=2), posted_at=datetime.now())
        db.session.add(entry)
        db.session.commit()
        entry_id = entry.id
        try:
            assert 'TEST_CP schon gepostet' not in [e.title for e in cp.due_entries()]
        finally:
            ContentCalendarEntry.query.filter_by(id=entry_id).delete()
            db.session.commit()



@pytest.fixture
def linkedin_publish_da(monkeypatch, tmp_path):
    fake = tmp_path / 'linkedin_publish.py'
    fake.write_text('# Attrappe', encoding='utf-8')
    monkeypatch.setattr(cp, 'LINKEDIN_PUBLISH', fake)
    return fake


def test_linkedin_ist_eine_content_platform_und_wird_gepostet():
    assert 'linkedin' in {p[0] for p in CONTENT_PLATFORMS}
    assert 'linkedin' in cp.PUBLISH_PLATFORMS


def test_linkedin_page_wird_gepostet_seit_12_10():
    assert 'linkedin_page' in cp.PUBLISH_PLATFORMS


def test_linkedin_page_kommandozeile_traegt_die_seite(app, bild, linkedin_publish_da, aufgezeichnet):
    calls, fake_run = aufgezeichnet
    fake_run.stdout = 'Dry-Run ok: Seite urn:li:organization:000000000'
    with app.app_context():
        ok, message = cp.publish_entry(_entry('linkedin_page', bild), dry_run=True)
    assert ok, message
    cmd = calls[0]
    assert cmd[cmd.index('--org') + 1] == cp.LINKEDIN_PAGE_BY_CONTACT[DW_CONTACT]
    assert '--publish' not in cmd


def test_linkedin_page_fremder_kontakt_wird_abgewiesen(app, bild, linkedin_publish_da, aufgezeichnet):
    calls, _ = aufgezeichnet
    with app.app_context():
        entry = _entry('linkedin_page', bild)
        entry.contact_id = 99999
        ok, message = cp.publish_entry(entry, dry_run=True)
    assert not ok and 'keine LinkedIn-Seite' in message
    assert calls == []


def test_linkedin_kommandozeile(app, bild, linkedin_publish_da, aufgezeichnet):
    calls, fake_run = aufgezeichnet
    fake_run.stdout = 'Dry-Run ok: Autor urn:li:person:x'
    with app.app_context():
        ok, message = cp.publish_entry(_entry('linkedin', bild), dry_run=True)
    assert ok, message
    assert len(calls) == 1
    cmd = calls[0]
    assert cmd[1] == str(linkedin_publish_da)
    assert '--caption-file' in cmd
    assert cmd.count('--image') == 1
    assert '--target' not in cmd and '--account' not in cmd
    assert '--org' not in cmd
    assert '--publish' not in cmd


def test_linkedin_publish_flag_nur_scharf(app, bild, linkedin_publish_da, aufgezeichnet):
    calls, fake_run = aufgezeichnet
    fake_run.stdout = 'OK https://www.linkedin.com/feed/update/urn:li:share:123/'
    with app.app_context():
        ok, message = cp.publish_entry(_entry('linkedin', bild), dry_run=False)
    assert ok and message == 'https://www.linkedin.com/feed/update/urn:li:share:123/'
    assert '--publish' in calls[0]


def test_linkedin_fremder_kontakt_wird_abgewiesen(app, bild, linkedin_publish_da, aufgezeichnet):
    calls, _ = aufgezeichnet
    with app.app_context():
        entry = _entry('linkedin', bild)
        entry.contact_id = 99999
        ok, message = cp.publish_entry(entry, dry_run=True)
    assert not ok and 'kein LinkedIn-Profil' in message
    assert calls == []


def test_linkedin_braucht_text(app, bild, linkedin_publish_da):
    with app.app_context():
        assert 'content_text' in cp.check_entry(_entry('linkedin', bild, text='  '))


def test_linkedin_mehrbild_geht_mit_jedem_bild(app, bild, linkedin_publish_da, aufgezeichnet):
    from pathlib import Path
    zweites = Path(bild).parent / 'b.png'
    zweites.write_bytes(b'x')
    calls, fake_run = aufgezeichnet
    fake_run.stdout = 'Dry-Run ok: Autor urn:li:person:x'
    with app.app_context():
        ok, message = cp.publish_entry(_entry('linkedin', bild, bilder=f"{bild};{zweites.name}"), dry_run=True)
    assert ok, message
    cmd = calls[0]
    assert [cmd[i + 1] for i, a in enumerate(cmd) if a == '--image'] == [str(bild), str(zweites)]


def test_linkedin_mehrbild_mit_fehlender_datei_gesperrt(app, bild, linkedin_publish_da):
    with app.app_context():
        reason = cp.check_entry(_entry('linkedin', bild, bilder=f"{bild};fehlt.png"))
        assert reason and 'fehlende Datei' in reason


def test_linkedin_textpost_ohne_bild(app, linkedin_publish_da, aufgezeichnet):
    calls, fake_run = aufgezeichnet
    fake_run.stdout = 'Dry-Run ok: Autor urn:li:person:x'
    with app.app_context():
        entry = _entry('linkedin', None, bilder='')
        assert cp.check_entry(entry) is None
        ok, message = cp.publish_entry(entry, dry_run=True)
    assert ok, message
    assert '--image' not in calls[0]


def test_linkedin_fehlschlag_wird_nicht_als_erfolg_gemeldet(app, bild, linkedin_publish_da, aufgezeichnet):
    calls, fake_run = aufgezeichnet

    class Fail:
        returncode = 2
        stdout = ''
        stderr = 'FEHLER: LinkedIn-Token abgelaufen'
    cp.subprocess.run = lambda cmd, **k: Fail()
    with app.app_context():
        ok, message = cp.publish_entry(_entry('linkedin', bild), dry_run=False)
    assert not ok and 'abgelaufen' in message



VERSPRICHT = 'Mehr dazu im Beitrag. Link im ersten Kommentar.'


def test_linkedin_versprochener_kommentar_ohne_notiz_wird_abgewiesen(app, bild, linkedin_publish_da, aufgezeichnet):
    calls, _ = aufgezeichnet
    with app.app_context():
        entry = _entry('linkedin', bild, text=VERSPRICHT)
        entry.notes = 'Link in den ersten Kommentar (Handgriff Max).'
        ok, message = cp.publish_entry(entry, dry_run=False)
    assert not ok and "Erster Kommentar:" in message
    assert calls == []


def test_linkedin_kommentar_aus_notiz_geht_mit(app, bild, linkedin_publish_da, aufgezeichnet):
    calls, fake_run = aufgezeichnet
    fake_run.stdout = 'OK https://www.linkedin.com/feed/update/urn:li:share:1/\nOK erster Kommentar gesetzt'
    with app.app_context():
        entry = _entry('linkedin', bild, text=VERSPRICHT)
        entry.notes = 'Vorlauf.\nErster Kommentar: https://musterwerkstatt.example/blog/x\nRest.'
        ok, message = cp.publish_entry(entry, dry_run=False)
    assert ok and message == 'https://www.linkedin.com/feed/update/urn:li:share:1/'
    cmd = calls[0]
    assert cmd[cmd.index('--comment') + 1] == 'https://musterwerkstatt.example/blog/x'


def test_linkedin_ohne_kommentar_kein_comment_flag(app, bild, linkedin_publish_da, aufgezeichnet):
    calls, _ = aufgezeichnet
    with app.app_context():
        cp.publish_entry(_entry('linkedin', bild), dry_run=True)
    assert '--comment' not in calls[0]


def test_linkedin_gescheiterter_kommentar_bleibt_ok_aber_laut(app, bild, linkedin_publish_da, aufgezeichnet):
    _, fake_run = aufgezeichnet
    fake_run.stdout = ('OK https://www.linkedin.com/feed/update/urn:li:share:1/\n'
                       'WARNUNG: erster Kommentar NICHT gesetzt (HTTP 403), von Hand nachtragen: x')
    with app.app_context():
        entry = _entry('linkedin', bild, text=VERSPRICHT)
        entry.notes = 'Erster Kommentar: x'
        ok, message = cp.publish_entry(entry, dry_run=False)
    assert ok and 'WARNUNG: erster Kommentar' in message


def test_linkedin_page_mit_kommentar_versprechen_wird_abgewiesen(app, bild, linkedin_publish_da, aufgezeichnet):
    calls, _ = aufgezeichnet
    with app.app_context():
        entry = _entry('linkedin_page', bild, text=VERSPRICHT)
        entry.notes = 'Erster Kommentar: x'
        ok, message = cp.publish_entry(entry, dry_run=True)
    assert not ok and 'Seitenweg' in message
    assert calls == []


def test_linkedin_karussell_slide_wird_abgewiesen(app, linkedin_publish_da, aufgezeichnet, tmp_path):
    calls, _ = aufgezeichnet
    slide = tmp_path / 'ig-lk1-slide1-hell_badge.png'
    slide.write_bytes(b'x')
    with app.app_context():
        ok, message = cp.publish_entry(_entry('linkedin', slide), dry_run=True)
    assert not ok and 'Karussell-Slide' in message
    assert calls == []


def test_due_entries_nimmt_linkedin_auf(app):
    with app.app_context():
        e = ContentCalendarEntry(platform='linkedin', title='TEST_CP faelliger LI-Post',
                                 status='scheduled', scheduled_for=datetime.now() - timedelta(hours=1))
        db.session.add(e)
        db.session.commit()
        try:
            assert 'TEST_CP faelliger LI-Post' in [x.title for x in cp.due_entries()]
        finally:
            ContentCalendarEntry.query.filter_by(id=e.id).delete()
            db.session.commit()



@pytest.fixture
def video(tmp_path):
    p = tmp_path / 'reel-1080x1920.mp4'
    p.write_bytes(b'kein-echtes-video')
    return p


def test_reel_kommandozeile_hat_video_und_kein_image(app, video, meta_publish_da, aufgezeichnet):
    calls, _ = aufgezeichnet
    with app.app_context():
        ok, message = cp.publish_entry(_entry('instagram', video), dry_run=True)
    assert ok, message
    cmd = calls[0]
    assert cmd[cmd.index('--video') + 1] == str(video)
    assert '--image' not in cmd and '--story' not in cmd
    assert '--caption-file' in cmd


def test_reel_auf_facebook_geht_ebenfalls_als_video(app, video, meta_publish_da, aufgezeichnet):
    calls, _ = aufgezeichnet
    with app.app_context():
        ok, _m = cp.publish_entry(_entry('facebook', video), dry_run=True)
    assert ok and '--video' in calls[0]
    assert calls[0][calls[0].index('--target') + 1] == 'fb'


def test_video_plus_bild_wird_abgewiesen(app, video, bild, meta_publish_da, aufgezeichnet):
    calls, _ = aufgezeichnet
    with app.app_context():
        ok, message = cp.publish_entry(_entry('instagram', video, bilder=f"{video};{bild}"), dry_run=True)
    assert not ok and 'genau EIN Video' in message
    assert calls == []


def test_video_story_wird_abgewiesen(app, video, meta_publish_da):
    with app.app_context():
        assert 'Video-Stories' in cp.check_entry(_entry(STORY_PLATFORM, video, text=''))


def test_linkedin_video_wird_abgewiesen(app, video, linkedin_publish_da, aufgezeichnet):
    calls, _ = aufgezeichnet
    with app.app_context():
        ok, message = cp.publish_entry(_entry('linkedin', video), dry_run=True)
    assert not ok and 'LinkedIn-Video' in message
    assert calls == []


def test_bild_bleibt_bild(app, bild, meta_publish_da, aufgezeichnet):
    calls, _ = aufgezeichnet
    with app.app_context():
        cp.publish_entry(_entry('instagram', bild), dry_run=True)
    assert '--image' in calls[0] and '--video' not in calls[0]



def test_asset_paths_loest_dateinamen_gegen_den_ersten_pfad_auf():
    ordner = os.path.join(os.path.abspath(os.sep), 'assets', 'w4')
    paths = cp.asset_paths(os.path.join(ordner, 'slide1.png') + ';slide2.png;slide3.png')
    assert len(paths) == 3
    assert all(str(p).startswith(ordner) for p in paths)


def test_asset_paths_leer_gibt_leere_liste():
    assert cp.asset_paths('') == []
    assert cp.asset_paths(None) == []




@pytest.fixture
def schalter(app):
    from models import CompanySettings

    def setzen(wert):
        with app.app_context():
            row = CompanySettings.query.get('content_autopost_enabled')
            if row is None:
                row = CompanySettings(key='content_autopost_enabled', value=wert)
                db.session.add(row)
            else:
                row.value = wert
            db.session.commit()

    yield setzen
    with app.app_context():
        CompanySettings.query.filter_by(key='content_autopost_enabled').delete()
        db.session.commit()


@pytest.fixture
def run_due_attrappe(monkeypatch):
    aufrufe = []
    monkeypatch.setattr(cp, 'run_due', lambda **kw: aufrufe.append(kw) or [])
    return aufrufe


def test_schalter_aus_postet_nicht(schalter, run_due_attrappe):
    schalter('0')
    import app as app_modul
    app_modul._autopost_on_start()
    assert run_due_attrappe == []


def test_unbekannter_schalterwert_postet_nicht(schalter, run_due_attrappe):
    for wert in ('', 'ja', 'true', '2'):
        schalter(wert)
        import app as app_modul
        app_modul._autopost_on_start()
    assert run_due_attrappe == []


def test_schalter_ein_postet_scharf(schalter, run_due_attrappe):
    schalter('1')
    import app as app_modul
    app_modul._autopost_on_start()
    assert run_due_attrappe == [{'dry_run': False}]


def test_hook_braucht_keinen_aktiven_app_context(schalter, run_due_attrappe):
    from flask import has_app_context
    schalter('1')
    assert not has_app_context()
    import app as app_modul
    app_modul._autopost_on_start()
    assert run_due_attrappe == [{'dry_run': False}]


def test_hook_haengt_nicht_am_import_von_app():
    import ast
    import app as app_modul
    with open(app_modul.__file__, encoding='utf-8') as f:
        baum = ast.parse(f.read())

    def aufrufe_in(knoten):
        return [n for n in ast.walk(knoten)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == '_autopost_on_start']

    main_bloecke = [n for n in baum.body
                    if isinstance(n, ast.If) and '__main__' in ast.dump(n.test)]
    assert len(main_bloecke) == 1, 'Kein eindeutiger __main__-Block in app.py'

    alle = aufrufe_in(baum)
    im_main = aufrufe_in(main_bloecke[0])
    assert len(alle) == 1, (
        f'{len(alle)} Aufrufe von _autopost_on_start() in app.py, erwartet genau '
        'einer. Ein zweiter auf Modulebene wuerde bei jedem Import posten.')
    assert len(im_main) == 1, (
        'Aufruf liegt nicht im __main__-Block -- damit postet jeder Import von '
        'app.py, also auch /zeit, /ende und pytest.')
