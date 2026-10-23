import os
import tempfile
import atexit

_fd, _TEST_DB_PATH = tempfile.mkstemp(prefix='stellwerk_test_', suffix='.db')
os.close(_fd)
os.remove(_TEST_DB_PATH)
os.environ['STELLWERK_DB_PATH'] = _TEST_DB_PATH

_TEST_PROFILES_DIR = tempfile.mkdtemp(prefix='stellwerk_test_profiles_')
os.environ['STELLWERK_PROFILES_DIR'] = _TEST_PROFILES_DIR

_TEST_KUNDEN_DIR = tempfile.mkdtemp(prefix='stellwerk_test_kunden_')
os.environ['STELLWERK_KUNDEN_DIRS'] = _TEST_KUNDEN_DIR
os.environ['STELLWERK_MEMORY_INDEX'] = os.path.join(_TEST_KUNDEN_DIR, 'MEMORY.md')

for _var, _name in (('STELLWERK_MEMORY_DIR', 'mem'), ('STELLWERK_PROZESSE_DIR', 'prozesse'),
                    ('STELLWERK_JOURNAL_DIR', 'journal')):
    os.environ[_var] = os.path.join(_TEST_KUNDEN_DIR, '_fehlt_' + _name)

os.environ['STELLWERK_INCOMING_PDF_DIR'] = tempfile.mkdtemp(prefix='stellwerk_test_belege_')


@atexit.register
def _cleanup_test_db():
    try:
        os.remove(_TEST_DB_PATH)
    except OSError:
        pass
    for ordner in (_TEST_PROFILES_DIR, _TEST_KUNDEN_DIR):
        try:
            os.rmdir(ordner)
        except OSError:
            pass


import sqlite3
import pytest


@pytest.fixture
def _keine_laufenden_laeufe():
    con = sqlite3.connect(os.environ['STELLWERK_DB_PATH'])
    con.execute("UPDATE fuell_jobs SET status = 'fertig' WHERE status = 'laeuft'")
    con.commit()
    con.close()
