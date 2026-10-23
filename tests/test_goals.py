import os
import sys
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import compute_goal_progress


def _inv(status, total_net, payment_date=None, doc_date=None):
    return SimpleNamespace(status=status, total_net=total_net,
                           payment_date=payment_date, date=doc_date)


def _goal(start, end):
    return SimpleNamespace(period_start=start, period_end=end)


MAY = _goal(date(2026, 5, 1), date(2026, 5, 31))


def test_paid_in_period_counts_to_achieved():
    invs = [_inv('paid', 1000, payment_date=date(2026, 5, 12))]
    r = compute_goal_progress(invs, MAY)
    assert r['achieved'] == 1000
    assert r['open_net'] == 0


def test_paid_outside_period_ignored():
    invs = [_inv('paid', 1000, payment_date=date(2026, 4, 30)),
            _inv('paid', 500, payment_date=date(2026, 6, 1))]
    r = compute_goal_progress(invs, MAY)
    assert r['achieved'] == 0


def test_cancelled_and_draft_ignored():
    invs = [_inv('cancelled', 1000, payment_date=date(2026, 5, 12)),
            _inv('draft', 1000, doc_date=date(2026, 5, 12))]
    r = compute_goal_progress(invs, MAY)
    assert r['achieved'] == 0
    assert r['open_net'] == 0


def test_paid_with_null_payment_date_ignored():
    invs = [_inv('paid', 1000, payment_date=None)]
    r = compute_goal_progress(invs, MAY)
    assert r['achieved'] == 0


def test_sent_and_overdue_count_to_open_by_date():
    invs = [_inv('sent', 300, doc_date=date(2026, 5, 5)),
            _inv('overdue', 200, doc_date=date(2026, 5, 20))]
    r = compute_goal_progress(invs, MAY)
    assert r['achieved'] == 0
    assert r['open_net'] == 500


def test_open_outside_period_ignored():
    invs = [_inv('sent', 300, doc_date=date(2026, 4, 5))]
    r = compute_goal_progress(invs, MAY)
    assert r['open_net'] == 0


def test_mixed_bucket():
    invs = [_inv('paid', 1000, payment_date=date(2026, 5, 12)),
            _inv('sent', 250, doc_date=date(2026, 5, 15)),
            _inv('paid', 999, payment_date=date(2026, 6, 2))]
    r = compute_goal_progress(invs, MAY)
    assert r['achieved'] == 1000
    assert r['open_net'] == 250


def test_empty_invoice_list():
    r = compute_goal_progress([], MAY)
    assert r['achieved'] == 0
    assert r['open_net'] == 0


def test_open_with_null_doc_date_ignored():
    invs = [_inv('sent', 300, doc_date=None)]
    r = compute_goal_progress(invs, MAY)
    assert r['open_net'] == 0
