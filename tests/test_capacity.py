import os
import sys
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import compute_capacity_projection

TODAY = date(2026, 7, 24)


def _ret(monthly_hours, start=date(2020, 1, 1), end=None, name='R'):
    return SimpleNamespace(monthly_hours=monthly_hours, start_date=start,
                           end_date=end, name=name)



def test_soll_is_weekly_times_weeks_per_month():
    p = compute_capacity_projection([], TODAY)
    assert p['soll_h'] == 86.6
    assert p['weekly_target'] == 20.0


def test_custom_weekly_target():
    p = compute_capacity_projection([], TODAY, weekly_target_mandate=30)
    assert p['soll_h'] == round(30 * 4.33, 1)



def test_horizon_length_default_12():
    assert len(compute_capacity_projection([], TODAY)['months']) == 12


def test_horizon_custom():
    assert len(compute_capacity_projection([], TODAY, months=6)['months']) == 6


def test_first_month_is_current_and_last_is_horizon_end():
    p = compute_capacity_projection([], TODAY)
    assert p['months'][0]['ym'] == '2026-07'
    assert p['months'][-1]['ym'] == '2027-06'


def test_month_rollover_into_next_year():
    p = compute_capacity_projection([], date(2026, 11, 15), months=4)
    assert [m['ym'] for m in p['months']] == ['2026-11', '2026-12', '2027-01', '2027-02']



def test_empty_retainers_all_free():
    p = compute_capacity_projection([], TODAY)
    for m in p['months']:
        assert m['planned_h'] == 0
        assert m['free_h'] == 86.6
        assert m['over'] is False
    assert p['current_free_h'] == 86.6
    assert p['min_free_h'] == 86.6
    assert p['first_relief_month'] is None



def test_open_ended_retainer_counts_every_month():
    p = compute_capacity_projection([_ret(10)], TODAY)
    for m in p['months']:
        assert m['planned_h'] == 10
        assert m['free_h'] == 76.6
    assert p['first_relief_month'] is None


def test_multiple_retainers_sum_and_sort_desc():
    p = compute_capacity_projection([_ret(5, name='Klein'), _ret(20, name='Gross')], TODAY)
    m0 = p['months'][0]
    assert m0['planned_h'] == 25
    assert [i['name'] for i in m0['items']] == ['Gross', 'Klein']



def test_retainer_drops_after_end_date_and_relief_detected():
    r = _ret(30, end=date(2026, 9, 30))
    p = compute_capacity_projection([r], TODAY)
    by_ym = {m['ym']: m for m in p['months']}
    assert by_ym['2026-09']['planned_h'] == 30
    assert by_ym['2026-10']['planned_h'] == 0
    assert p['first_relief_month'] == by_ym['2026-10']['label']


def test_end_date_midmonth_still_counts_that_month():
    r = _ret(10, end=date(2026, 9, 10))
    by_ym = {m['ym']: m for m in compute_capacity_projection([r], TODAY)['months']}
    assert by_ym['2026-09']['planned_h'] == 10
    assert by_ym['2026-10']['planned_h'] == 0



def test_future_start_not_counted_before_start():
    r = _ret(15, start=date(2026, 10, 1))
    by_ym = {m['ym']: m for m in compute_capacity_projection([r], TODAY)['months']}
    assert by_ym['2026-07']['planned_h'] == 0
    assert by_ym['2026-09']['planned_h'] == 0
    assert by_ym['2026-10']['planned_h'] == 15


def test_start_midmonth_counts_that_month():
    r = _ret(15, start=date(2026, 10, 20))
    by_ym = {m['ym']: m for m in compute_capacity_projection([r], TODAY)['months']}
    assert by_ym['2026-09']['planned_h'] == 0
    assert by_ym['2026-10']['planned_h'] == 15



def test_over_budget_month_flagged_negative_free():
    p = compute_capacity_projection([_ret(100)], TODAY)
    m0 = p['months'][0]
    assert m0['over'] is True
    assert m0['free_h'] == -13.4
    assert m0['pct'] > 100
    assert p['current_free_h'] == -13.4



def test_zero_and_none_hours_skipped():
    rs = [_ret(0, name='Null'), _ret(None, name='None'), _ret(10, name='Echt')]
    m0 = compute_capacity_projection(rs, TODAY)['months'][0]
    assert m0['planned_h'] == 10
    assert [i['name'] for i in m0['items']] == ['Echt']



def test_small_relief_below_threshold_not_flagged():
    r = _ret(3, end=date(2026, 8, 31))
    assert compute_capacity_projection([r], TODAY)['first_relief_month'] is None
