import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from backup import BACKUP_DIR, DB_PATH

CORE_TABLES = ['contacts', 'documents', 'time_entries', 'tasks', 'retainers']

LOG_PATH = Path(__file__).parent / 'data' / 'restore_drill.log'

TRUNCATION_RATIO = 0.5

STALE_DAYS = 7


def find_latest_backup():
    if not BACKUP_DIR.exists():
        return None
    backups = sorted(
        BACKUP_DIR.glob('crm_*.db'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return backups[0] if backups else None


def ro_connect(path):
    return sqlite3.connect(f'file:{Path(path).as_posix()}?mode=ro', uri=True)


def count_rows(conn, table):
    try:
        return conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    except sqlite3.Error:
        return -1


def run_drill():
    lines = []

    def emit(text=''):
        lines.append(text)
        print(text)

    stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    emit(f'=== Restore-Probe {stamp} ===')

    backup = find_latest_backup()
    if backup is None:
        emit(f'FEHLER: Kein Backup gefunden in {BACKUP_DIR}')
        emit('Verdikt: FEHLGESCHLAGEN (kein Backup vorhanden)')
        _write_log(lines)
        return 1

    age = datetime.now() - datetime.fromtimestamp(backup.stat().st_mtime)
    size_mb = backup.stat().st_size / (1024 * 1024)
    emit(f'Backup: {backup.name} ({size_mb:.1f} MB, {age.days} Tage alt)')
    emit(f'Ort:    {BACKUP_DIR}')

    problems = []
    if age.days >= STALE_DAYS:
        emit(f'HINWEIS: Backup ist {age.days} Tage alt (>= {STALE_DAYS}). '
             'backup.py laeuft moeglicherweise nicht.')

    tmp_dir = Path(tempfile.mkdtemp(prefix='restore_drill_'))
    tmp_db = tmp_dir / 'restore_probe.db'
    probe = None
    try:
        shutil.copy2(backup, tmp_db)

        integrity = None
        try:
            probe = ro_connect(tmp_db)
            integrity = probe.execute('PRAGMA integrity_check').fetchone()[0]
        except sqlite3.DatabaseError as e:
            emit('')
            emit(f'Integritaets-Check: FEHLER ({e})')
            problems.append(f'Backup nicht als SQLite lesbar: {e}')

        if integrity is not None:
            emit('')
            emit(f'Integritaets-Check: {integrity}')
            if integrity != 'ok':
                problems.append('integrity_check nicht ok')

            live = ro_connect(DB_PATH)
            emit('')
            emit(f'{"Tabelle":<14} {"Backup":>8} {"Live":>8} {"Delta":>8}  Status')
            emit('-' * 52)
            for table in CORE_TABLES:
                b = count_rows(probe, table)
                l = count_rows(live, table)
                if b < 0:
                    status = 'FEHLT'
                    problems.append(f'{table}: Tabelle im Backup nicht lesbar')
                elif b == 0:
                    status = 'LEER'
                    problems.append(f'{table}: leer im Backup')
                elif l > 0 and b < l * TRUNCATION_RATIO:
                    status = 'VERDACHT'
                    problems.append(
                        f'{table}: nur {b} von {l} Zeilen (Trunkierung?)')
                else:
                    status = 'OK'
                delta = (b - l) if (b >= 0 and l >= 0) else 0
                emit(f'{table:<14} {b:>8} {l:>8} {delta:>+8}  {status}')
            live.close()

            try:
                newest_doc = probe.execute(
                    'SELECT MAX(date) FROM documents').fetchone()[0]
            except sqlite3.Error:
                newest_doc = None
            emit('')
            emit(f'Juengstes Dokument-Datum im Backup: {newest_doc or "-"}')
    finally:
        if probe is not None:
            probe.close()
        shutil.rmtree(tmp_dir, ignore_errors=True)

    emit('')
    if problems:
        emit(f'Verdikt: PROBLEM ({len(problems)})')
        for p in problems:
            emit(f'  - {p}')
        _write_log(lines)
        return 1

    emit('Verdikt: OK. Backup ist wiederherstellbar und vollstaendig.')
    _write_log(lines)
    return 0


def _write_log(lines):
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n\n')
    except OSError as e:
        print(f'(Logdatei nicht geschrieben: {e})', file=sys.stderr)


if __name__ == '__main__':
    sys.exit(run_drill())
