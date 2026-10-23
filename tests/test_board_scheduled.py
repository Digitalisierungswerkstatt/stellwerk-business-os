import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from models import BOARD_SCHEDULED_LEAD_DAYS, Task, db
from app import app as flask_app

LEAD = BOARD_SCHEDULED_LEAD_DAYS


def _seed(title, status="todo", due_offset_days=None):
    with flask_app.app_context():
        due = date.today() + timedelta(days=due_offset_days) if due_offset_days is not None else None
        t = Task(title=title, status=status, due_date=due)
        db.session.add(t)
        db.session.commit()
        return t.id


def test_far_future_task_hidden_from_board_and_listed_in_scheduled():
    _seed("SCHED-weit-zukunft", due_offset_days=LEAD + 30)
    with flask_app.test_client() as client:
        board = client.get("/board").data.decode("utf-8")
        assert "SCHED-weit-zukunft" not in board

        scheduled = client.get("/board/scheduled")
        assert scheduled.status_code == 200
        assert "SCHED-weit-zukunft" in scheduled.data.decode("utf-8")


def test_task_within_lead_window_stays_on_board():
    _seed("SCHED-im-vorlauf", due_offset_days=max(LEAD - 2, 0))
    with flask_app.test_client() as client:
        board = client.get("/board").data.decode("utf-8")
        assert "SCHED-im-vorlauf" in board
        scheduled = client.get("/board/scheduled").data.decode("utf-8")
        assert "SCHED-im-vorlauf" not in scheduled


def test_task_without_due_date_stays_on_board():
    _seed("SCHED-ohne-datum", due_offset_days=None)
    with flask_app.test_client() as client:
        board = client.get("/board").data.decode("utf-8")
        assert "SCHED-ohne-datum" in board


def test_done_task_with_future_due_not_in_scheduled():
    _seed("SCHED-erledigt-zukunft", status="erledigt", due_offset_days=LEAD + 30)
    with flask_app.test_client() as client:
        scheduled = client.get("/board/scheduled").data.decode("utf-8")
        assert "SCHED-erledigt-zukunft" not in scheduled


def test_search_still_finds_future_task():
    _seed("SCHED-suchbar-zukunft", due_offset_days=LEAD + 60)
    with flask_app.test_client() as client:
        assert "SCHED-suchbar-zukunft" not in client.get("/board").data.decode("utf-8")
        found = client.get("/board?search=SCHED-suchbar-zukunft").data.decode("utf-8")
        assert "SCHED-suchbar-zukunft" in found


def test_board_shows_terminiert_link_when_scheduled_tasks_exist():
    _seed("SCHED-badge-trigger", due_offset_days=LEAD + 10)
    with flask_app.test_client() as client:
        board = client.get("/board").data.decode("utf-8")
        assert "/board/scheduled" in board
        assert "Terminiert" in board
