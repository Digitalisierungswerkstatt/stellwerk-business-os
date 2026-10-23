import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = REPO / 'templates'

FREMD_SKRIPT = re.compile(r'<script\b[^>]*\bsrc=["\'](https?://[^"\']+)["\'][^>]*>')
VENDOR = re.compile(r"filename='(vendor/[^']+)'")


def test_kein_debugger_fest_eingeschaltet():
    for name in ('app.py', 'start_demo.py'):
        text = (REPO / name).read_text(encoding='utf-8')
        assert not re.search(r'\.run\([^)]*debug\s*=\s*True|app\.debug\s*=\s*True', text), \
            f'{name}: Debugger fest eingeschaltet'


def test_fremde_skripte_versioniert_mit_sri():
    fehler = []
    for pfad in TEMPLATES.rglob('*.html'):
        for m in FREMD_SKRIPT.finditer(pfad.read_text(encoding='utf-8')):
            tag, url = m.group(0), m.group(1)
            rel = pfad.relative_to(REPO).as_posix()
            if not re.search(r'@\d+\.\d+\.\d+/', url):
                fehler.append(f'{rel}: ohne exakte Version: {url}')
            if 'integrity="sha384-' not in tag or 'crossorigin=' not in tag:
                fehler.append(f'{rel}: ohne SRI: {url}')
    assert not fehler, '\n'.join(fehler)


def test_vendor_dateien_vorhanden():
    for pfad in TEMPLATES.rglob('*.html'):
        for datei in VENDOR.findall(pfad.read_text(encoding='utf-8')):
            assert (REPO / 'static' / datei).is_file(), f'{pfad.name}: static/{datei} fehlt'
