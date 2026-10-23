import re

_KONSONANT = 'bcdfghjklmnprstvwxyzßBCDFGHJKLMNPRSTVWXYZ'

DIGRAF_RE = re.compile(
    r'(?:(?<![A-Za-zÄÖÜäöüß])|(?<=[' + _KONSONANT + r']))'
    r'[aouAOU]e'
    r'(?=[A-Za-zÄÖÜäöüß])'
)

_UMLAUT = {'ae': 'ä', 'oe': 'ö', 'ue': 'ü',
           'Ae': 'Ä', 'Oe': 'Ö', 'Ue': 'Ü'}

WORT_RE = re.compile(r'[A-Za-zÄÖÜäöüß]+')


AUSNAHMEN = (
    'tuell', 'duell', 'nuell', 'suell', 'xuell', 'tuett', 'nuett',
    'zuerst', 'zueinander', 'zuerkenn', 'zueign',
    'oebene',
    'statue',
    'michael', 'raphael', 'rafael', 'ismael', 'israel',
    'manuel', 'samuel', 'emanuel', 'ruediger', 'pueblo', 'boeing', 'caesar',
    'bonhoeff',
    'poet', 'poesi', 'koex', 'koeffizi', 'koedukat', 'aero', 'maestro',
    'does', 'tuesday', 'aesthet', 'true', 'bluepr', 'bluesky',
)


WORTLISTE_TYPOS = {
    'strasse': 'Straße',
    'strassen': 'Straßen',
    'massnahme': 'Maßnahme',
    'massnahmen': 'Maßnahmen',
    'gemaess': 'gemäß',
    'seitenmass': 'Seitenmaß',
    'menue': 'Menü',
}


URLISH_RE = re.compile(
    r'[a-z][a-z0-9+.\-]*://[^\s<>"\']+'
    r'|//[^\s<>"\']+'
    r'|[\w\-]+(?:\.[\w\-]+)+/[^\s<>"\']*'
    r'|(?<![\w.])/[\w./~%+\-]{2,}'
    r'|(?<![\w/])[\w\-]+'
    r'\.(?:html?|php|css|js|json|xml|webp|png|jpe?g|svg|pdf'
    r'|md|py|txt|csv|tsv|xlsx?|docx?|pptx?|zip|ya?ml|sql|cjs|mjs|ts|vbs|bat)\b'
    r'|(?<![\w.])[\w.]*_[\w.]*'
    r'|(?<!\w)(?=[0-9a-f]*[0-9])[0-9a-f]{7,}(?!\w)',
    re.IGNORECASE)


def _ausgenommen(wort_klein: str, idx: int) -> bool:
    for frag in AUSNAHMEN:
        start = 0
        while True:
            pos = wort_klein.find(frag, start)
            if pos < 0:
                break
            if pos <= idx < pos + len(frag):
                return True
            start = pos + 1
    return False


def _vorschlag(wort: str, stellen: list) -> str:
    teile, i = [], 0
    for s in stellen:
        teile.append(wort[i:s])
        teile.append(_UMLAUT[wort[s:s + 2]])
        i = s + 2
    teile.append(wort[i:])
    return ''.join(teile)


def find_ascii_umlauts(text, scrub_urls: bool = True) -> list:
    if not text:
        return []
    src = URLISH_RE.sub(' ', text) if scrub_urls else text
    treffer = []
    for m in WORT_RE.finditer(src):
        wort = m.group()
        klein = wort.lower()
        if klein in WORTLISTE_TYPOS:
            treffer.append((wort, WORTLISTE_TYPOS[klein]))
            continue
        stellen = [d.start() for d in DIGRAF_RE.finditer(wort)
                   if not _ausgenommen(klein, d.start())]
        if stellen:
            treffer.append((wort, _vorschlag(wort, stellen)))
    return treffer



_CLI_KOPF = [
    "umlaut_lint: prueft die REGEL, nicht das Gate.",
    "  Deliverable pruefen -> python deliverable_check.py <datei>",
    "  (das Gate raeumt Mockups, Zitate und Markup vorher weg)",
]

_FIXTURE = "tests/fixtures/umlaut_faelle.tsv"
_TAB = chr(9)


def _lies_fixture(pfad):
    faelle = []
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        if not zeile.strip() or zeile.lstrip().startswith("#"):
            continue
        teile = zeile.split(_TAB)
        if len(teile) != 4 or teile[0] == "erwartung":
            continue
        faelle.append(tuple(teile))
    return faelle


def selbsttest(out=print, pfad=None):
    import pathlib
    pfad = (pathlib.Path(pfad) if pfad
            else pathlib.Path(__file__).resolve().parent / _FIXTURE)
    if not pfad.exists():
        out("FIXTURE FEHLT: " + str(pfad))
        out("Die Fixture gehoert nicht zu diesem Repo,")
        out("--selbsttest braucht eine eigene Datei mit Faellen.")
        return 2
    faelle = _lies_fixture(pfad)
    stumm, laut, schuld, geheilt = [], [], [], []
    for erwartung, text, klasse, _herkunft in faelle:
        hits = find_ascii_umlauts(text)
        if erwartung == "treffer" and not hits:
            stumm.append((text, klasse))
        elif erwartung == "sauber" and hits:
            laut.append((text, klasse))
        elif erwartung == "fehlalarm":
            (schuld if hits else geheilt).append((text, klasse))
    out("Selbsttest gegen " + pfad.name + ": " + str(len(faelle)) + " Faelle")
    if stumm:
        out("  ROT  Positivkontrolle schweigt (" + str(len(stumm)) + "): "
            + ", ".join(t + " [" + k + "]" for t, k in stumm))
    if laut:
        out("  ROT  geschlossene Klasse wieder offen (" + str(len(laut)) + "): "
            + ", ".join(t + " [" + k + "]" for t, k in laut))
    if schuld:
        klassen = sorted({k for _, k in schuld})
        out("  bekannte Fehlalarme, unveraendert: " + str(len(schuld)) + " in "
            + str(len(klassen)) + " Klassen (" + ", ".join(klassen) + ")")
    if geheilt:
        out("  NEU  bekannter Fehlalarm ist still (" + str(len(geheilt)) + "): "
            + ", ".join(t + " [" + k + "]" for t, k in geheilt))
        out("       Wenn das gewollt war: Fixture-Zeile auf sauber drehen.")
    if not stumm and not laut:
        out("  gruen: Regel greift, geschlossene Klassen bleiben zu.")
    return 1 if (stumm or laut) else 0


def _main(argv):
    import pathlib
    import sys as _sys
    flags = {a for a in argv if a.startswith("--")}
    ziele = [a for a in argv if not a.startswith("--")]

    if flags & {"--hilfe", "--help"}:
        for z in _CLI_KOPF:
            print(z)
        print("")
        print("Aufruf:")
        print("  python umlaut_lint.py <datei> [<datei> ...]   Dateien pruefen")
        print("  python umlaut_lint.py -                       stdin pruefen")
        print("  python umlaut_lint.py --selbsttest            Regel gegen die Fixture messen")
        print("Exit: 0 = keine Treffer, 1 = Treffer bzw. Regression, 2 = Aufruffehler.")
        return 0

    for z in _CLI_KOPF:
        print(z)
    print("")

    if "--selbsttest" in flags:
        return selbsttest()

    if not ziele:
        print("Kein Ziel angegeben. --hilfe zeigt den Aufruf.")
        return 2

    gesamt = 0
    for ziel in ziele:
        if ziel == "-":
            name, text = "<stdin>", _sys.stdin.read()
        else:
            pfad = pathlib.Path(ziel)
            if not pfad.exists():
                print("FEHLT: " + ziel)
                return 2
            name = str(pfad)
            text = pfad.read_text(encoding="utf-8", errors="replace")
        hits = find_ascii_umlauts(text)
        eindeutig = dict(hits)
        gesamt += len(eindeutig)
        if eindeutig:
            print(name + ": " + str(len(hits)) + " Treffer, "
                  + str(len(eindeutig)) + " eindeutig")
            for gefunden, korrekt in eindeutig.items():
                print("    " + gefunden + " -> " + korrekt)
        else:
            print(name + ": sauber")
    return 1 if gesamt else 0


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
