import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import models
from models import TASK_STALE_THRESHOLD_DAYS, Task


def _task(*, status="todo", days_ago=0, updated_at="__set__", title="Alterungs-Test"):
    t = Task(title=title, status=status)
    if updated_at == "__set__":
        t.updated_at = datetime.now() - timedelta(days=days_ago)
    else:
        t.updated_at = updated_at
    return t



def test_days_since_update_counts_calendar_days():
    assert _task(days_ago=40).days_since_update == 40


def test_days_since_update_none_when_updated_at_missing():
    assert _task(updated_at=None).days_since_update is None


def test_is_stale_true_for_old_open_task():
    assert _task(status="todo", days_ago=40).is_stale is True


def test_is_stale_false_for_recent_open_task():
    assert _task(status="todo", days_ago=5).is_stale is False


def test_is_stale_false_at_exact_threshold():
    assert _task(status="todo", days_ago=TASK_STALE_THRESHOLD_DAYS).is_stale is False


def test_is_stale_true_one_day_past_threshold():
    assert _task(status="todo", days_ago=TASK_STALE_THRESHOLD_DAYS + 1).is_stale is True


def test_is_stale_false_for_done_task_regardless_of_age():
    assert _task(status="erledigt", days_ago=400).is_stale is False


def test_is_stale_false_when_updated_at_missing():
    assert _task(updated_at=None).is_stale is False


def test_threshold_is_thirty_days():
    assert TASK_STALE_THRESHOLD_DAYS == 30


from app import app as flask_app
from models import db


def _seed_task(title, status, days_ago):
    with flask_app.app_context():
        t = Task(title=title, status=status)
        db.session.add(t)
        db.session.commit()
        stamp = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
        db.session.execute(
            db.text("UPDATE tasks SET updated_at = :s WHERE id = :i"),
            {"s": stamp, "i": t.id},
        )
        db.session.commit()
        return t.id


def test_board_renders_stale_marker_for_old_open_task():
    _seed_task("BADGE-stale Leiche", "todo", days_ago=45)
    with flask_app.test_client() as client:
        resp = client.get("/board")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "BADGE-stale Leiche" in body
        assert "ohne Aktualisierung" in body


def test_cleanup_route_lists_open_tasks_oldest_first_and_excludes_done():
    stale_id = _seed_task("CLEANUP-alt-stale", "todo", days_ago=90)
    fresh_id = _seed_task("CLEANUP-frisch", "todo", days_ago=1)
    done_id = _seed_task("CLEANUP-erledigt-alt", "erledigt", days_ago=200)
    with flask_app.test_client() as client:
        resp = client.get("/board/cleanup")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert "CLEANUP-alt-stale" in body
        assert "CLEANUP-frisch" in body
        assert "CLEANUP-erledigt-alt" not in body
        assert body.index("CLEANUP-alt-stale") < body.index("CLEANUP-frisch")


def test_cleanup_route_offers_erledigt_and_backlog_actions():
    tid = _seed_task("CLEANUP-actions", "todo", days_ago=60)
    with flask_app.test_client() as client:
        body = client.get("/board/cleanup").data.decode("utf-8")
        assert f"/board/tasks/{tid}/move" in body
        assert "erledigt" in body
        assert "backlog" in body
