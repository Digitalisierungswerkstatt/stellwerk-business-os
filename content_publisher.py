import os
import re
import sys
import argparse
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from models import db, ContentCalendarEntry

META_PUBLISH = Path(os.path.expanduser("~")) / "scripts" / "meta_publish.py"

META_TARGETS = {'instagram': 'ig', 'facebook': 'fb', 'instagram_story': 'ig'}

STORY_PLATFORMS = {'instagram_story'}

META_ACCOUNT_BY_CONTACT = {
    315: 'musterwerkstatt',
}

LINKEDIN_PUBLISH = Path(os.path.expanduser("~")) / "scripts" / "linkedin_publish.py"
LINKEDIN_TARGETS = {'linkedin': 'person', 'linkedin_page': 'organization'}
LINKEDIN_MAX_IMAGES = 20

LINKEDIN_ACCOUNT_BY_CONTACT = {315: 'max'}

LINKEDIN_PAGE_BY_CONTACT = {315: 'urn:li:organization:000000000'}

PUBLISH_PLATFORMS = set(META_TARGETS) | set(LINKEDIN_TARGETS)

RELEASED_STATUS = 'scheduled'

VIDEO_SUFFIXES = {'.mp4', '.mov'}


def is_video(path):
    return Path(path).suffix.lower() in VIDEO_SUFFIXES


def asset_paths(asset_link):
    parts = [p.strip() for p in (asset_link or '').split(';') if p.strip()]
    if not parts:
        return []
    first = Path(parts[0])
    paths = [first]
    for raw in parts[1:]:
        cand = Path(raw)
        paths.append(cand if cand.is_absolute() else first.parent / cand)
    return paths


def due_entries(now=None):
    now = now or datetime.now()
    return (ContentCalendarEntry.query
            .filter(ContentCalendarEntry.status == RELEASED_STATUS,
                    ContentCalendarEntry.posted_at.is_(None),
                    ContentCalendarEntry.outbox_job.is_(None),
                    ContentCalendarEntry.scheduled_for.isnot(None),
                    ContentCalendarEntry.scheduled_for <= now,
                    ContentCalendarEntry.platform.in_(tuple(PUBLISH_PLATFORMS)))
            .order_by(ContentCalendarEntry.scheduled_for)
            .all())


def check_entry(entry):
    if entry.platform in LINKEDIN_TARGETS:
        return check_linkedin(entry)
    if entry.platform not in META_TARGETS:
        return f"Plattform '{entry.platform}' laeuft nicht ueber den Meta-Direktweg"
    if entry.contact_id not in META_ACCOUNT_BY_CONTACT:
        return (f"Kontakt {entry.contact_id} ist keinem Meta-Konto zugeordnet "
                f"(META_ACCOUNT_BY_CONTACT in content_publisher.py)")
    is_story = entry.platform in STORY_PLATFORMS
    if not is_story and not (entry.content_text or '').strip():
        return "content_text ist leer, es gibt keine Caption"
    paths = asset_paths(entry.asset_link)
    if not paths:
        return "asset_link ist leer, es gibt kein Bild"
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        return f"asset_link zeigt auf {len(missing)} fehlende Datei(en): {'; '.join(missing)}"
    if any(is_video(p) for p in paths):
        if is_story:
            return "Video-Stories sind nicht gebaut, eine Story nimmt hier nur ein Bild"
        if len(paths) != 1:
            return (f"Ein Reel ist genau EIN Video, asset_link nennt {len(paths)} Datei(en). "
                    "Video und Bilder lassen sich nicht mischen.")
    if is_story and len(paths) > 1:
        return (f"Eine Story nimmt genau EIN Bild, asset_link nennt {len(paths)}. "
                "Mehrteilige Stories sind eigene Eintraege, kein Karussell.")
    if not is_story and len(paths) > 10:
        return f"Ein IG-Karussell nimmt maximal 10 Bilder, hier sind {len(paths)}"
    if not META_PUBLISH.is_file():
        return f"meta_publish.py fehlt: {META_PUBLISH}"
    return None


FIRST_COMMENT = re.compile(r'^Erster Kommentar:\s*(\S.*)$', re.MULTILINE)
PROMISES_COMMENT = re.compile(r'\bersten Kommentar\b', re.IGNORECASE)
CAROUSEL_SLIDE = re.compile(r'slide', re.IGNORECASE)


def first_comment(entry):
    m = FIRST_COMMENT.search(entry.notes or '')
    return m.group(1).strip() if m else None


def check_linkedin(entry):
    if PROMISES_COMMENT.search(entry.content_text or ''):
        if entry.platform == 'linkedin_page':
            return ("Text verspricht einen ersten Kommentar, der Seitenweg kann keinen "
                    "posten. Link anders unterbringen oder als Profilpost einplanen.")
        if not first_comment(entry):
            return ("Text verspricht einen ersten Kommentar, in den Notizen fehlt die Zeile "
                    "'Erster Kommentar: <text>'. Ohne sie geht der Post ohne Link raus.")
    if entry.platform == 'linkedin_page':
        if entry.contact_id not in LINKEDIN_PAGE_BY_CONTACT:
            return (f"Kontakt {entry.contact_id} hat keine LinkedIn-Seite im Direktweg "
                    f"(LINKEDIN_PAGE_BY_CONTACT in content_publisher.py)")
    elif entry.contact_id not in LINKEDIN_ACCOUNT_BY_CONTACT:
        return (f"Kontakt {entry.contact_id} hat kein LinkedIn-Profil im Direktweg "
                f"(LINKEDIN_ACCOUNT_BY_CONTACT in content_publisher.py)")
    if not (entry.content_text or '').strip():
        return "content_text ist leer, es gibt keinen Post-Text"
    paths = asset_paths(entry.asset_link)
    if len(paths) > LINKEDIN_MAX_IMAGES:
        return f"LinkedIn nimmt hoechstens {LINKEDIN_MAX_IMAGES} Bilder, asset_link nennt {len(paths)}"
    if not paths:
        return None if LINKEDIN_PUBLISH.is_file() else f"linkedin_publish.py fehlt: {LINKEDIN_PUBLISH}"
    for path in paths:
        if not path.is_file():
            return f"asset_link zeigt auf eine fehlende Datei: {path}"
        if is_video(path):
            return "LinkedIn-Video ist im Direktweg nicht gebaut, nur Bilder"
    if len(paths) == 1 and CAROUSEL_SLIDE.search(paths[0].name):
        return (f"{paths[0].name} ist eine Karussell-Slide, als Einzelbild fehlt das "
                "Karussell dahinter (Wisch-Hinweis ins Leere). Eigene LinkedIn-Fassung "
                "ohne Wisch-Hinweis anlegen und ohne 'slide' im Namen ablegen.")
    if not LINKEDIN_PUBLISH.is_file():
        return f"linkedin_publish.py fehlt: {LINKEDIN_PUBLISH}"
    return None


def needs_caption(entry):
    return entry.platform not in STORY_PLATFORMS


def output_kind(entry):
    if entry.platform in LINKEDIN_TARGETS:
        return 'linkedin'
    return 'meta_story' if entry.platform in STORY_PLATFORMS else 'meta'


def build_command(entry, caption_path, media, dry_run=True):
    if entry.platform in LINKEDIN_TARGETS:
        cmd = [sys.executable, str(LINKEDIN_PUBLISH), '--caption-file', caption_path]
        cmd += [arg for p in media for arg in ('--image', p)]
        if entry.platform == 'linkedin_page':
            cmd += ['--org', LINKEDIN_PAGE_BY_CONTACT[entry.contact_id]]
        comment = first_comment(entry)
        if comment:
            cmd += ['--comment', comment]
    else:
        cmd = [sys.executable, str(META_PUBLISH),
               '--account', META_ACCOUNT_BY_CONTACT[entry.contact_id],
               '--target', META_TARGETS[entry.platform]]
        if entry.platform in STORY_PLATFORMS:
            cmd.append('--story')
        else:
            cmd += ['--caption-file', caption_path]
        if is_video(media[0]):
            cmd += ['--video', media[0]]
        else:
            for path in media:
                cmd += ['--image', path]
    if not dry_run:
        cmd.append('--publish')
    return cmd


def interpret_output(kind, returncode, out):
    script = 'linkedin_publish.py' if kind == 'linkedin' else 'meta_publish.py'
    if returncode != 0:
        tail = out[-400:] if out else f"returncode {returncode}, keine Ausgabe"
        return False, f"{script} fehlgeschlagen: {tail}"
    if kind == 'linkedin':
        link = re.search(r'https://www\.linkedin\.com/feed/update/\S+', out)
        message = link.group(0) if link else (out.splitlines()[-1] if out else 'ok')
        warn = re.search(r'^WARNUNG: erster Kommentar.*$', out, re.MULTILINE)
        return True, (f"{message} | {warn.group(0)}" if warn else message)
    if kind == 'meta_story':
        media = re.search(r'media (\d+)', out)
        return True, (f"Story media {media.group(1)} (Highlight und Sticker nur in der App)"
                      if media else 'ok')
    link = re.search(r'https://www\.(instagram|facebook)\.com/\S+', out)
    return True, (link.group(0) if link else 'ok')


def publish_entry(entry, dry_run=True):
    reason = check_entry(entry)
    if reason:
        return False, reason
    kind = output_kind(entry)
    script = 'linkedin_publish.py' if kind == 'linkedin' else 'meta_publish.py'
    tmp = None
    try:
        if needs_caption(entry):
            with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False,
                                             encoding='utf-8') as fh:
                fh.write(entry.content_text.strip())
                tmp = fh.name
        cmd = build_command(entry, tmp, [str(p) for p in asset_paths(entry.asset_link)],
                            dry_run=dry_run)
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=300)
        out = ((proc.stdout or '') + (proc.stderr or '')).strip()
        return interpret_output(kind, proc.returncode, out)
    except subprocess.TimeoutExpired:
        where = 'das Profil' if kind == 'linkedin' else 'die Plattform'
        return False, f"{script} lief in den Timeout (300 s) -- Zustand UNKLAR, vor einem zweiten Lauf {where} ansehen"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def mark_posted(entry, message, via=None, when=None):
    entry.status = 'posted'
    entry.posted_at = when or datetime.now(timezone.utc).replace(tzinfo=None)
    local = entry.posted_at.replace(tzinfo=timezone.utc).astimezone()
    note = (f"Automatisch gepostet{f' ({via})' if via else ''} "
            f"{local.strftime('%d.%m.%Y %H:%M')}: {message}")
    entry.notes = f"{entry.notes}\n{note}" if entry.notes else note


def run_due(dry_run=True, now=None):
    results = []
    for entry in due_entries(now=now):
        ok, message = publish_entry(entry, dry_run=dry_run)
        if ok and not dry_run:
            mark_posted(entry, message)
            db.session.commit()
        results.append((entry, ok, message))
    return results


def main():
    ap = argparse.ArgumentParser(description="Faellige Content-Kalender-Eintraege posten")
    ap.add_argument('--publish', action='store_true',
                    help="VEROEFFENTLICHT wirklich (ohne das Flag: Dry-Run)")
    ap.add_argument('--at', help="Stichtag YYYY-MM-DD[THH:MM] statt jetzt")
    args = ap.parse_args()

    now = None
    if args.at:
        for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d'):
            try:
                now = datetime.strptime(args.at, fmt)
                break
            except ValueError:
                continue
        if now is None:
            sys.exit(f"--at nicht lesbar: {args.at}")

    from app import app
    with app.app_context():
        if args.publish and not args.at:
            try:
                import content_outbox
                content_outbox.print_report(content_outbox.sync())
            except Exception as exc:
                print(f"Cloud-Abgleich uebersprungen: {type(exc).__name__}: {exc}")
        results = run_due(dry_run=not args.publish, now=now)
        mode = 'PUBLISH' if args.publish else 'DRY-RUN'
        ref = (now or datetime.now()).strftime('%d.%m.%Y %H:%M')
        print(f"[{mode}] Stichtag {ref}: {len(results)} faellige(r) Eintrag/Eintraege")
        if not results:
            print("  nichts faellig (Status 'scheduled', Termin erreicht, noch nicht gepostet)")
        for entry, ok, message in results:
            flag = 'OK  ' if ok else 'FEHL'
            when = entry.scheduled_for.strftime('%d.%m. %H:%M') if entry.scheduled_for else '--'
            print(f"  {flag} #{entry.id} {when} {entry.platform:<10} {entry.title[:40]}")
            print(f"       {message}")
        if not args.publish and results:
            print("\n  Dry-Run. Mit --publish wird veroeffentlicht.")


if __name__ == '__main__':
    main()
