import argparse
import hashlib
import importlib.util
import json
import secrets
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from models import db, ContentCalendarEntry, CompanySettings
import content_publisher as cp

SOCIAL_OUTBOX = Path.home() / 'scripts' / 'social_outbox.py'
SWITCH = 'content_outbox_enabled'
ENV_HASH_KEY = 'content_outbox_env_hash'
RUNNER_REPO = 'your-org/your-runner-repo'
RUNNER_SECRET = 'DW_RUNNER_ENV'

RUNNER_ENV_KEYS = (
    'META_ACCESS_TOKEN', 'FTP_HOST', 'FTP_USER', 'FTP_PASS',
    'LINKEDIN_PUBLISH_ACCESS_TOKEN', 'LINKEDIN_PUBLISH_EXPIRES_AT', 'LINKEDIN_PUBLISH_PERSON_URN',
    'LINKEDIN_COMMUNITY_ACCESS_TOKEN', 'LINKEDIN_COMMUNITY_EXPIRES_AT',
    'TELEGRAM_BOT_TOKEN', 'TELEGRAM_ALLOWED_CHAT_IDS',
)

PICKUP_GRACE = timedelta(hours=2)
WITHDRAWN_STATUS = 'visual_fertig'
LOCK_KEY = 'content_outbox_lock'
LOCK_STALE = timedelta(minutes=20)
ORPHAN_AFTER = timedelta(minutes=10)

_proto = None


def proto():
    global _proto
    if _proto is None:
        spec = importlib.util.spec_from_file_location('social_outbox', SOCIAL_OUTBOX)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _proto = mod
    return _proto


def default_store():
    return proto().FtpStore.from_env()


class OutboxBusy(Exception):
    pass


def enabled():
    return CompanySettings.get(SWITCH) == '1'


def _utc(local_naive):
    return local_naive.astimezone(timezone.utc)


def _note(entry, text):
    line = f"Cloud {datetime.now().strftime('%d.%m.%Y %H:%M')}: {text}"
    entry.notes = f"{entry.notes}\n{line}" if entry.notes else line


def fingerprint(entry):
    h = hashlib.sha256()
    for part in (entry.platform, entry.contact_id, entry.content_text or '',
                 entry.asset_link or '', entry.scheduled_for.isoformat() if entry.scheduled_for else '',
                 cp.first_comment(entry) or ''):
        h.update(str(part).encode('utf-8') + b'\0')
    for path in cp.asset_paths(entry.asset_link):
        try:
            st = path.stat()
            h.update(f"{st.st_size}:{int(st.st_mtime)}".encode())
        except OSError:
            h.update(b'fehlt')
    return h.hexdigest()[:8]


def job_fingerprint(job):
    parts = (job or '').split('-')
    return parts[2] if len(parts) == 4 and parts[0].startswith('e') else None


def _acquire(wait_s):
    db.session.execute(db.text("INSERT OR IGNORE INTO company_settings (key, value) VALUES (:k, '')"),
                       {'k': LOCK_KEY})
    db.session.commit()
    deadline = time.monotonic() + wait_s
    while True:
        now = datetime.now(timezone.utc)
        res = db.session.execute(db.text(
            "UPDATE company_settings SET value = :now WHERE key = :k AND (value = '' OR value < :stale)"),
            {'now': now.isoformat(), 'k': LOCK_KEY, 'stale': (now - LOCK_STALE).isoformat()})
        db.session.commit()
        if res.rowcount == 1:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(2)


def _release():
    db.session.execute(db.text("UPDATE company_settings SET value = '' WHERE key = :k"), {'k': LOCK_KEY})
    db.session.commit()


def _remove_quietly(store, job):
    try:
        store.remove_job(job)
    except Exception:
        pass



def exportable(now=None):
    now = now or datetime.now()
    E = ContentCalendarEntry
    return (E.query
            .filter(E.status == cp.RELEASED_STATUS,
                    E.posted_at.is_(None),
                    E.outbox_job.is_(None),
                    E.scheduled_for.isnot(None),
                    E.scheduled_for > now,
                    E.platform.in_(tuple(cp.PUBLISH_PLATFORMS)))
            .order_by(E.scheduled_for)
            .all())


def build_job(entry, probe=False):
    P = proto()
    paths = cp.asset_paths(entry.asset_link)
    names = [f"m{i}_{p.name}" for i, p in enumerate(paths)]
    files = {n: p.read_bytes() for n, p in zip(names, paths)}
    caption = None
    if cp.needs_caption(entry):
        files[P.CAPTION] = entry.content_text.strip().encode('utf-8')
        caption = f"{P.PLACEHOLDER}/{P.CAPTION}"
    cmd = cp.build_command(entry, caption, [f"{P.PLACEHOLDER}/{n}" for n in names],
                           dry_run=probe)
    script = Path(cmd[1])
    due = datetime.now() if probe else entry.scheduled_for
    job = (f"{'probe' if probe else 'e'}{entry.id}-{entry.scheduled_for:%Y%m%d%H%M}-"
           f"{fingerprint(entry)}-{secrets.token_hex(2)}")
    meta = {
        'v': 1, 'job': job, 'entry_id': entry.id, 'title': entry.title,
        'platform': entry.platform, 'kind': cp.output_kind(entry),
        'due_utc': P.iso(_utc(due)), 'due_local': entry.scheduled_for.strftime('%d.%m.%Y %H:%M'),
        'script': script.name, 'script_sha256': P.script_hash(script),
        'args': cmd[2:], 'files': sorted(files),
        'reel': any(cp.is_video(p) for p in paths),
        'exported_at': P.iso(P.now_utc()), 'probe': probe,
    }
    return meta, files


def upload_job(store, meta, files):
    P = proto()
    job = meta['job']
    try:
        for name, data in files.items():
            store.put(job, name, data)
        store.put(job, P.JOB, json.dumps(meta, ensure_ascii=False, indent=1).encode('utf-8'))
    except Exception:
        _remove_quietly(store, job)
        raise


def export_entry(entry, store):
    reason = cp.check_entry(entry)
    if reason:
        return False, reason
    meta, files = build_job(entry)
    upload_job(store, meta, files)
    entry.outbox_job = meta['job']
    _note(entry, f"in die Warteschlange gelegt (Job {meta['job']}), GitHub postet zum Termin.")
    db.session.commit()
    return True, meta['job']


def export_pending(store, now=None):
    results = []
    for entry in exportable(now):
        try:
            ok, message = export_entry(entry, store)
        except Exception as exc:
            db.session.rollback()
            ok, message = False, f"{type(exc).__name__}: {exc}"
        results.append((entry, ok, message))
    return results



def _claim_stale(store, job, now):
    P = proto()
    try:
        since = P.parse_utc(json.loads(store.get(job, P.CLAIMED))['claimed_at'])
    except Exception:
        return True
    return now - since > P.STALE_AFTER


def _unclear(entry, store, job, why):
    entry.status = WITHDRAWN_STATUS
    entry.outbox_job = None
    _note(entry, f"Lauf UNKLAR ({why}). Freigabe zurückgenommen: erst auf der Plattform "
                 "nachsehen, ob der Post draußen ist, dann neu freigeben oder auf Posted setzen.")
    _remove_quietly(store, job)


def apply_result(entry, store, job):
    P = proto()
    res = json.loads(store.get(job, P.RESULT))
    if res.get('unclear'):
        _unclear(entry, store, job, res.get('output', '')[-200:])
        return 'UNKLAR'
    ok, message = cp.interpret_output(res['kind'], res['returncode'], res.get('output', ''))
    if ok:
        when = P.parse_utc(res['finished_utc']).replace(tzinfo=None)
        cp.mark_posted(entry, message, via='Cloud', when=when)
    else:
        _note(entry, f"Post fehlgeschlagen: {message} Bleibt freigegeben, der Laptop "
                     "versucht es beim nächsten Lauf.")
    entry.outbox_job = None
    _remove_quietly(store, job)
    return message if ok else 'fehlgeschlagen'


def import_results(store, now=None, notify=None):
    P = proto()
    now = now or P.now_utc()
    notify = notify or P.telegram
    report = []
    pending = (ContentCalendarEntry.query
               .filter(ContentCalendarEntry.outbox_job.isnot(None)).all())
    for entry in pending:
        job = entry.outbox_job
        try:
            files = store.files(job)
            if P.RESULT in files:
                report.append((entry, 'abgeglichen', apply_result(entry, store, job)))
            elif not files:
                entry.outbox_job = None
                _note(entry, f"Job {job} fehlt in der Warteschlange, der Laptop übernimmt.")
                report.append((entry, 'fehlte', 'lokal weiter'))
            elif P.CLAIMED in files:
                if not _claim_stale(store, job, now):
                    continue
                _unclear(entry, store, job, 'Runner hat übernommen und kein Ergebnis geliefert')
                report.append((entry, 'UNKLAR', 'Freigabe zurückgenommen'))
            elif P.JOB not in files:
                _remove_quietly(store, job)
                entry.outbox_job = None
                _note(entry, f"Job {job} ohne Auslöser, der Laptop übernimmt.")
                report.append((entry, 'kaputt', 'lokal weiter'))
            elif (P.JOB in files and entry.scheduled_for
                  and _utc(entry.scheduled_for) + PICKUP_GRACE < now):
                if not store.delete(job, P.JOB):
                    continue
                _remove_quietly(store, job)
                entry.outbox_job = None
                _note(entry, "vom GitHub-Runner nicht abgeholt, der Laptop postet lokal.")
                notify(f"GitHub-Runner hat #{entry.id} \"{entry.title[:50]}\" nicht abgeholt "
                       f"(fällig {entry.scheduled_for:%d.%m. %H:%M}). Der Laptop übernimmt. "
                       "Actions prüfen: github.com/your-org/your-runner-repo/actions")
                report.append((entry, 'NICHT ABGEHOLT', 'lokal weiter'))
            else:
                continue
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            report.append((entry, 'FEHLER', f"{type(exc).__name__}: {exc}"))
    return report


def refresh_changed(store, now=None):
    report = []
    pending = (ContentCalendarEntry.query
               .filter(ContentCalendarEntry.outbox_job.isnot(None)).all())
    for entry in pending:
        if entry.status != cp.RELEASED_STATUS or entry.posted_at is not None:
            reason = 'nicht mehr freigegeben'
        elif fingerprint(entry) != job_fingerprint(entry.outbox_job):
            reason = 'geändert'
        else:
            continue
        try:
            withdraw(entry, store, now=now)
            _note(entry, f"Job zurückgezogen ({reason}, außerhalb der Eintragsmaske).")
            report.append((entry, 'zurückgezogen', reason))
            db.session.commit()
        except OutboxBusy as exc:
            db.session.commit()
            report.append((entry, 'BUSY', str(exc)))
        except Exception as exc:
            db.session.rollback()
            report.append((entry, 'FEHLER', f"{type(exc).__name__}: {exc}"))
    return report


def sweep_orphans(store, now=None):
    P = proto()
    now = now or P.now_utc()
    known = {e.outbox_job for e in ContentCalendarEntry.query
             .filter(ContentCalendarEntry.outbox_job.isnot(None)).all()}
    report = []
    for job in store.list_jobs():
        if job in known or not job.startswith('e'):
            continue
        if P.JOB not in store.files(job):
            continue
        try:
            age = now - P.parse_utc(json.loads(store.get(job, P.JOB))['exported_at'])
        except Exception:
            continue
        if age >= ORPHAN_AFTER and store.delete(job, P.JOB):
            _remove_quietly(store, job)
            report.append(job)
    return report



def withdraw(entry, store, now=None):
    P = proto()
    job = entry.outbox_job
    if not job:
        return None
    if store.delete(job, P.JOB):
        _remove_quietly(store, job)
        entry.outbox_job = None
        return 'zurückgezogen'
    files = store.files(job)
    if not files:
        entry.outbox_job = None
        return 'Job fehlte schon'
    if P.RESULT in files:
        message = apply_result(entry, store, job)
        raise OutboxBusy(f"Die Cloud hat diesen Eintrag schon verarbeitet ({message}). "
                         "Stand übernommen, Änderung NICHT gespeichert.")
    if P.CLAIMED in files and _claim_stale(store, job, now or P.now_utc()):
        _unclear(entry, store, job, 'Runner hat übernommen und kein Ergebnis geliefert')
        return 'hängender Job entfernt'
    raise OutboxBusy("Der Cloud-Runner postet diesen Eintrag gerade. Änderung NICHT "
                     "gespeichert, in ein paar Minuten erneut versuchen.")



def runner_env_text():
    from dotenv import dotenv_values
    vals = dotenv_values(Path.home() / '.env')
    return ''.join(f"{k}='{vals[k]}'\n" for k in RUNNER_ENV_KEYS if vals.get(k))


def push_runner_env(force=False):
    text = runner_env_text()
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    if not force and CompanySettings.get(ENV_HASH_KEY) == digest:
        return 'unverändert'
    proc = subprocess.run(['gh', 'secret', 'set', RUNNER_SECRET, '-R', RUNNER_REPO],
                          input=text, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        return f"gh secret set fehlgeschlagen: {(proc.stderr or proc.stdout).strip()[:200]}"
    row = CompanySettings.query.get(ENV_HASH_KEY)
    if row is None:
        db.session.add(CompanySettings(key=ENV_HASH_KEY, value=digest))
    else:
        row.value = digest
    db.session.commit()
    return 'aktualisiert'



def sync(store=None, now=None, export=True, notify=None, lock_wait=120):
    on = enabled()
    pending = ContentCalendarEntry.query.filter(
        ContentCalendarEntry.outbox_job.isnot(None)).count()
    report = {'enabled': on, 'imported': [], 'refreshed': [], 'orphans': [], 'exported': [],
              'env': None, 'skipped': None}
    if not on and not pending:
        return report
    if not _acquire(lock_wait):
        report['skipped'] = 'ein anderer Abgleich läuft gerade'
        return report
    own = store is None
    try:
        store = store or default_store()
        report['imported'] = import_results(store, notify=notify)
        report['refreshed'] = refresh_changed(store)
        report['orphans'] = sweep_orphans(store)
        if export and on:
            report['exported'] = export_pending(store, now=now)
    finally:
        if own and store is not None:
            store.close()
        _release()
    if on:
        try:
            report['env'] = push_runner_env()
        except Exception as exc:
            report['env'] = f"fehlgeschlagen: {type(exc).__name__}: {exc}"
    return report


def print_report(report):
    if report.get('skipped'):
        print(f"Cloud-Warteschlange: ausgelassen, {report['skipped']}")
        return
    if not report['enabled'] and not report['imported']:
        return
    print(f"Cloud-Warteschlange ({'ein' if report['enabled'] else 'AUS'}): "
          f"{len(report['imported'])} abgeglichen, {len(report['refreshed'])} zurückgezogen, "
          f"{len(report['orphans'])} verwaist, {len(report['exported'])} abgelegt"
          + (f", Secret {report['env']}" if report['env'] else ''))
    for entry, state, message in report['imported'] + report['refreshed']:
        print(f"  {state:<14} #{entry.id} {entry.title[:40]}: {message}")
    for job in report['orphans']:
        print(f"  {'verwaist':<14} {job} entfernt")
    for entry, ok, message in report['exported']:
        print(f"  {'abgelegt' if ok else 'NICHT abgelegt':<14} #{entry.id} {entry.title[:40]}: {message}")



def main():
    ap = argparse.ArgumentParser(description="Cloud-Warteschlange des Content-Kalenders")
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('sync')
    sub.add_parser('status')
    p = sub.add_parser('probe')
    p.add_argument('entry_id', type=int)
    w = sub.add_parser('withdraw')
    w.add_argument('entry_id', type=int)
    sub.add_parser('withdraw-all')
    e = sub.add_parser('push-env')
    e.add_argument('--force', action='store_true')
    args = ap.parse_args()

    from app import app
    with app.app_context():
        if args.cmd == 'sync':
            report = sync()
            print_report(report)
            if not report['enabled'] and not report['imported']:
                print("Schalter aus, keine offenen Jobs: nichts zu tun.")
        elif args.cmd == 'push-env':
            print(push_runner_env(force=args.force))
        elif args.cmd == 'status':
            pending = ContentCalendarEntry.query.filter(
                ContentCalendarEntry.outbox_job.isnot(None)).order_by(
                ContentCalendarEntry.scheduled_for).all()
            print(f"Schalter: {'ein' if enabled() else 'aus'} · {len(pending)} Eintrag/Einträge in der Cloud")
            for entry in pending:
                print(f"  #{entry.id} {entry.scheduled_for:%d.%m. %H:%M} {entry.platform:<10} "
                      f"{entry.title[:40]} -> {entry.outbox_job}")
            store = default_store()
            try:
                jobs = store.list_jobs()
                print(f"Ablage: {len(jobs)} Job(s)")
                for job in jobs:
                    print(f"  {job}: {', '.join(sorted(store.files(job)))}")
            finally:
                store.close()
        else:
            store = default_store()
            try:
                if args.cmd == 'probe':
                    entry = db.session.get(ContentCalendarEntry, args.entry_id)
                    reason = cp.check_entry(entry) if entry else 'Eintrag nicht gefunden'
                    if reason:
                        sys.exit(f"Probe nicht möglich: {reason}")
                    meta, files = build_job(entry, probe=True)
                    upload_job(store, meta, files)
                    print(f"Probe-Job {meta['job']} abgelegt (ohne --publish, sofort fällig).")
                    print("  Runner: nächster Cron-Lauf oder Actions > social-outbox > Run workflow")
                elif args.cmd == 'withdraw':
                    entry = db.session.get(ContentCalendarEntry, args.entry_id)
                    print(withdraw(entry, store))
                    db.session.commit()
                else:
                    for entry in ContentCalendarEntry.query.filter(
                            ContentCalendarEntry.outbox_job.isnot(None)).all():
                        try:
                            print(f"#{entry.id}: {withdraw(entry, store)}")
                        except OutboxBusy as exc:
                            print(f"#{entry.id}: {exc}")
                        db.session.commit()
            finally:
                store.close()


if __name__ == '__main__':
    main()
