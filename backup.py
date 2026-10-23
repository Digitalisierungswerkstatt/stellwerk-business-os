import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
PROD_DB_PATH = BASE_DIR / 'data' / 'crm.db'
DB_PATH = Path(os.environ.get('STELLWERK_DB_PATH') or PROD_DB_PATH)
BACKUP_DIR = Path(__file__).resolve().parent / 'backups'
MAX_BACKUPS = 30


def latest_backup():
    if not BACKUP_DIR.exists():
        return None
    backups = sorted(BACKUP_DIR.glob('crm_*.db'), key=lambda p: p.stat().st_mtime, reverse=True)
    return backups[0] if backups else None


TRAGENDE_TABELLEN = ('time_entries', 'tasks', 'contacts', 'documents')


def _zeilen(con):
    return {t: con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
            for t in TRAGENDE_TABELLEN}


def create_backup(label=None):
    if not DB_PATH.exists():
        print(f'Datenbank nicht gefunden: {DB_PATH}')
        return False

    src = sqlite3.connect(f'file:{DB_PATH.as_posix()}?mode=ro', uri=True)

    integrity = src.execute('PRAGMA integrity_check').fetchone()[0]
    if integrity != 'ok':
        print(f'ABBRUCH: integrity_check meldet Probleme: {integrity}', file=sys.stderr)
        print('Kein Backup erstellt -- Live-DB pruefen, bevor weitergemacht wird.', file=sys.stderr)
        src.close()
        return False

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    suffix = f'_{label}' if label else ''
    backup_name = f'crm_{timestamp}{suffix}.db'
    backup_path = BACKUP_DIR / backup_name

    try:
        dest = sqlite3.connect(str(backup_path))
        with dest:
            src.backup(dest)
        kopie, quelle = _zeilen(dest), _zeilen(src)
        dest.close()
        size_mb = backup_path.stat().st_size / (1024 * 1024)
        print(f'Backup erstellt: {backup_path} ({size_mb:.1f} MB)')
        print('  Zeilen Kopie/Quelle: ' + ', '.join(
            f'{t} {kopie[t]}/{quelle[t]}' for t in TRAGENDE_TABELLEN))
        fehlend = [t for t in TRAGENDE_TABELLEN if kopie[t] < quelle[t]]
        if fehlend:
            print(f'  WARNUNG: Kopie hat weniger Zeilen in {", ".join(fehlend)}. '
                  f'Vor dem Eingriff erneut sichern.', file=sys.stderr)
            return False
    except Exception as e:
        print(f'Backup fehlgeschlagen: {e}', file=sys.stderr)
        return False
    finally:
        src.close()

    cleanup_old_backups()
    return True


def cleanup_old_backups():
    if not BACKUP_DIR.exists():
        return

    backups = sorted(BACKUP_DIR.glob('crm_*.db'), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[MAX_BACKUPS:]:
        old.unlink()
        print(f'  Altes Backup gelöscht: {old.name}')


def check_last_backup():
    if not BACKUP_DIR.exists():
        print('Noch keine Backups vorhanden.')
        return

    backups = sorted(BACKUP_DIR.glob('crm_*.db'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not backups:
        print('Noch keine Backups vorhanden.')
        return

    latest = backups[0]
    age = datetime.now() - datetime.fromtimestamp(latest.stat().st_mtime)
    size_mb = latest.stat().st_size / (1024 * 1024)
    print(f'Letztes Backup: {latest.name} ({size_mb:.1f} MB)')
    print(f'Alter: {age.days} Tage, {age.seconds // 3600} Stunden')
    print(f'Backups gesamt: {len(backups)}')

    if age.days >= 1:
        print(f'\n  Empfehlung: Backup ist {age.days} Tage alt — bitte "python backup.py" ausführen.')


if __name__ == '__main__':
    if '--check' in sys.argv:
        check_last_backup()
    else:
        label = None
        if '--label' in sys.argv:
            i = sys.argv.index('--label')
            label = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
            if not label or not all(c.isalnum() or c in '_-' for c in label):
                print('--label braucht einen Namen aus Buchstaben, Ziffern, _ oder -',
                      file=sys.stderr)
                sys.exit(2)
        sys.exit(0 if create_backup(label) else 1)
