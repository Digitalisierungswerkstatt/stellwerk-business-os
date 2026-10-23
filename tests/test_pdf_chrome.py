import os
import re
import shutil
import subprocess

import pytest

import app as app_module


class _HaengenderProzess:

    def __init__(self):
        self.returncode = -9
        self.gekillt = False

    def communicate(self, timeout=None):
        if timeout is not None:
            raise subprocess.TimeoutExpired(cmd='node', timeout=timeout)
        return ('', '')

    def kill(self):
        self.gekillt = True


def _popen_der_nach_dem_schreiben_haengt(pdf_inhalt, protokoll):

    def fabrik(args, **kwargs):
        script = args[2]
        protokoll['script'] = script
        ziel = re.search(r"path: '([^']+\.pdf)'", script).group(1)
        with open(ziel, 'wb') as f:
            f.write(pdf_inhalt)
        prozess = _HaengenderProzess()
        protokoll['prozess'] = prozess
        return prozess

    return fabrik


def test_chrome_path_wird_beim_import_aufgeloest():
    if app_module._resolve_chrome_path() is None:
        pytest.skip('Auf diesem Geraet ist weder System-Chrome noch ein Cache-Build vorhanden')

    pfad = os.environ.get('PUPPETEER_EXECUTABLE_PATH')
    assert pfad, 'PUPPETEER_EXECUTABLE_PATH ist nach dem Import von app.py nicht gesetzt'
    assert os.path.exists(pfad), f'Aufgeloester Chrome-Pfad existiert nicht: {pfad}'


def test_env_uebersteuerung_gewinnt(monkeypatch):
    monkeypatch.setenv('PUPPETEER_EXECUTABLE_PATH', 'X:/eigener/chrome.exe')
    app_module._export_chrome_path()
    assert os.environ['PUPPETEER_EXECUTABLE_PATH'] == 'X:/eigener/chrome.exe'


def test_generate_pdf_liefert_echte_pdf_bytes():
    if shutil.which('node') is None:
        pytest.skip('node nicht im PATH')
    if app_module._resolve_chrome_path() is None:
        pytest.skip('kein Chrome auffindbar')

    pdf_bytes, error = app_module._generate_pdf('<h1>Rauchtest</h1><p>Grüße, Maß, Öl</p>')

    assert error is None, f'PDF-Erzeugung meldete einen Fehler: {error}'
    assert pdf_bytes, 'PDF-Erzeugung lieferte leere Bytes'
    assert pdf_bytes[:4] == b'%PDF', f'Ausgabe ist kein PDF, beginnt mit {pdf_bytes[:16]!r}'
    assert pdf_bytes.rstrip()[-5:] == b'%%EOF', \
        f'PDF endet nicht auf %%EOF, sondern auf {pdf_bytes[-16:]!r}'


def test_schliessen_wird_nach_drei_sekunden_aufgegeben(monkeypatch):
    protokoll = {}
    monkeypatch.setattr(subprocess, 'Popen',
                        _popen_der_nach_dem_schreiben_haengt(b'%PDF-1.4\n%%EOF\n', protokoll))

    app_module._generate_pdf('<h1>Struktur</h1>')

    script = protokoll['script']
    assert 'Promise.race' in script, 'Kein Zeitlimit um browser.close() herum'
    assert 'setTimeout(resolve, 3000)' in script, 'Zeitlimit fuer close() ist nicht 3 s'
    assert 'process.exit(0)' in script, 'Prozess wird nach dem PDF nicht beendet'
    assert script.index('page.pdf') < script.index('Promise.race'), \
        'Das Zeitlimit steht vor dem PDF-Schreiben — dann rettet es nichts'


def test_timeout_liefert_fertiges_pdf_trotzdem_aus(monkeypatch):
    fertig = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\nstartxref\n0\n%%EOF\n'
    protokoll = {}
    monkeypatch.setattr(subprocess, 'Popen',
                        _popen_der_nach_dem_schreiben_haengt(fertig, protokoll))

    pdf_bytes, error = app_module._generate_pdf('<h1>Rettung</h1>')

    assert error is None, f'Fertiges PDF wurde verworfen: {error}'
    assert pdf_bytes == fertig
    assert protokoll['prozess'].gekillt, 'Der haengende Node-Prozess wurde nicht beendet'


def test_timeout_liefert_kein_halbes_pdf_aus(monkeypatch):
    halb = b'%PDF-1.4\n1 0 obj\n<<>>\nendo'
    protokoll = {}
    monkeypatch.setattr(subprocess, 'Popen',
                        _popen_der_nach_dem_schreiben_haengt(halb, protokoll))

    pdf_bytes, error = app_module._generate_pdf('<h1>Abgeschnitten</h1>')

    assert pdf_bytes is None, 'Ein unvollstaendiges PDF wurde ausgeliefert'
    assert error == 'PDF-Generierung: Timeout nach 60 Sekunden.'


def test_fertiges_pdf_oder_none_kennt_seine_grenzen(tmp_path):
    ganz = b'%PDF-1.4\nInhalt\nstartxref\n0\n%%EOF\n'

    fehlt = tmp_path / 'gibtsnicht.pdf'
    assert app_module._fertiges_pdf_oder_none(str(fehlt)) is None

    vollstaendig = tmp_path / 'ganz.pdf'
    vollstaendig.write_bytes(ganz)
    assert app_module._fertiges_pdf_oder_none(str(vollstaendig)) == ganz

    ohne_trailer = tmp_path / 'halb.pdf'
    ohne_trailer.write_bytes(b'%PDF-1.4\nInhalt\nstartx')
    assert app_module._fertiges_pdf_oder_none(str(ohne_trailer)) is None

    kein_pdf = tmp_path / 'fremd.pdf'
    kein_pdf.write_bytes(b'<html>Fehlerseite</html>')
    assert app_module._fertiges_pdf_oder_none(str(kein_pdf)) is None


def _kontakt_fuer_infrastruktur():
    from app import Contact, db

    with app_module.app.app_context():
        kontakt = Contact(organisation='Infrastruktur Testfirma', vorname='I', nachname='T')
        db.session.add(kontakt)
        db.session.commit()
        return kontakt.id


def test_infrastruktur_pdf_liefert_fertiges_pdf_trotz_timeout(monkeypatch):
    fertig = b'%PDF-1.4\nInfrastruktur\nstartxref\n0\n%%EOF\n'

    def fake_run(args, **kwargs):
        ziel = re.search(r"path: '([^']+\.pdf)'", args[2]).group(1)
        with open(ziel, 'wb') as f:
            f.write(fertig)
        raise subprocess.TimeoutExpired(cmd='node', timeout=60)

    monkeypatch.setattr(subprocess, 'run', fake_run)
    kontakt_id = _kontakt_fuer_infrastruktur()

    with app_module.app.test_client() as client:
        antwort = client.get(f'/contacts/{kontakt_id}/infrastruktur-pdf')

    assert antwort.status_code == 200, f'Erwartet 200, bekam {antwort.status_code}'
    assert antwort.data == fertig


def test_infrastruktur_pdf_timeout_endet_nicht_im_serverfehler(monkeypatch):

    def fake_run(args, **kwargs):
        raise subprocess.TimeoutExpired(cmd='node', timeout=60)

    monkeypatch.setattr(subprocess, 'run', fake_run)
    kontakt_id = _kontakt_fuer_infrastruktur()

    with app_module.app.test_client() as client:
        antwort = client.get(f'/contacts/{kontakt_id}/infrastruktur-pdf')

    assert antwort.status_code == 302, \
        f'Timeout muss zur Kontaktseite zurueckleiten, bekam {antwort.status_code}'
    assert f'/contacts/{kontakt_id}' in antwort.headers['Location']


class _FertigerLauf:

    returncode = 0
    stdout = ''
    stderr = ''


def test_infrastruktur_pdf_laesst_keine_temp_datei_liegen(monkeypatch):
    fertig = b'%PDF-1.4\nInfrastruktur\nstartxref\n0\n%%EOF\n'
    gesehen = {}

    def fake_run(args, **kwargs):
        ziel = re.search(r"path: '([^']+\.pdf)'", args[2]).group(1)
        gesehen['pdf'] = ziel.replace('/', os.sep)
        gesehen['html'] = gesehen['pdf'][:-4] + '.html'
        with open(ziel, 'wb') as f:
            f.write(fertig)
        return _FertigerLauf()

    monkeypatch.setattr(subprocess, 'run', fake_run)
    kontakt_id = _kontakt_fuer_infrastruktur()

    with app_module.app.test_client() as client:
        antwort = client.get(f'/contacts/{kontakt_id}/infrastruktur-pdf')

    assert antwort.status_code == 200, f'Erwartet 200, bekam {antwort.status_code}'
    assert antwort.data == fertig, 'Das ausgelieferte Dokument muss das erzeugte sein'
    assert not os.path.exists(gesehen['html']), \
        f'Temp-HTML liegt noch: {gesehen["html"]}'
    assert not os.path.exists(gesehen['pdf']), \
        f'Temp-PDF liegt noch: {gesehen["pdf"]}'


def test_generate_pdf_meldet_fehler_auch_bei_oem_stderr(monkeypatch):
    if shutil.which('node') is None:
        pytest.skip('node nicht im PATH')

    attrappe = ('process.stderr.write(Buffer.from('
                '[0x61,0x75,0x73,0x67,0x65,0x66,0x81,0x68,0x72,0x74])); process.exit(1);')
    echt = subprocess.Popen
    monkeypatch.setattr(subprocess, 'Popen',
                        lambda args, **kw: echt(['node', '-e', attrappe], **kw))

    pdf_bytes, error = app_module._generate_pdf('<h1>egal</h1>')

    assert pdf_bytes is None, 'Ohne PDF darf nichts zurueckgegeben werden'
    assert isinstance(error, str), f'Die Fehlermeldung muss ein Text sein, war {type(error).__name__}'
    assert error.startswith('PDF-Fehler:'), f'Unerwartete Meldung: {error!r}'
