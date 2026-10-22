import random
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app import domain
from app.domain import settle, week_start


def pact(i, stake, target, done, user=None):
    return {"id": i, "user_id": user or i, "stake": stake, "target_days": target, "done_days": done}


def test_losers_pay_and_winners_share_by_exposure():
    # loser misses 2 days at 50k -> pool 100k, fee 12k, 88k shared by exposure 30k : 150k
    d, fee, charity = settle([pact(1, 50_000, 4, 2), pact(2, 10_000, 3, 3), pact(3, 30_000, 5, 6)])
    assert d == {1: -100_000, 2: 14_666, 3: 73_333} and (fee, charity) == (12_000, 1)


def test_nobody_wins_everything_after_fee_goes_to_charity():
    d, fee, charity = settle([pact(1, 20_000, 2, 1)])
    assert d == {1: -20_000} and fee + charity == 20_000


def test_payout_is_capped_at_three_times_own_exposure():
    d, fee, charity = settle([pact(1, 1_000_000, 7, 0), pact(2, 10_000, 1, 1)])  # tiny winner, huge pool
    assert d[2] == 3 * 10_000 and d[1] == -7_000_000 and charity == 7_000_000 - fee - d[2]


def test_nobody_pays_more_than_they_hold():
    d, _, _ = settle([pact(1, 100_000, 5, 0, user=9), pact(2, 100_000, 5, 5, user=8)], balances={9: 120_000, 8: 0})
    assert d[1] == -120_000


def test_money_is_conserved_for_random_weeks():
    rnd = random.Random(1)
    for _ in range(500):
        ps = [pact(i, rnd.randrange(10_000, 1_000_000, 10_000), n := rnd.randint(1, 7), rnd.randint(0, n), user=rnd.randint(1, 4)) for i in range(rnd.randint(1, 12))]
        bal = {u: rnd.randrange(0, 5_000_000) for u in range(1, 5)} if rnd.random() < 0.5 else None
        d, fee, charity = settle(ps, bal)
        assert sum(d.values()) + fee + charity == 0 and fee >= 0 and charity >= 0
        if bal is not None:
            for u in bal:
                assert sum(v for i, v in d.items() if ps[i]["user_id"] == u and v < 0) >= -bal[u]


def test_week_starts_on_saturday():
    assert week_start(date(2026, 9, 23)) == date(2026, 9, 19)
    assert week_start(date(2026, 9, 19)) == date(2026, 9, 19)
    assert week_start(date(2026, 9, 25)) == date(2026, 9, 19)  # Friday is the last day


def test_tehran_midnight_boundary(monkeypatch):
    class Fake(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 16, 21, 0, tzinfo=timezone.utc).astimezone(tz)  # 00:30 on the 17th in Tehran

    monkeypatch.setattr(domain, "datetime", Fake)
    assert domain.today(ZoneInfo("Asia/Tehran")) == date(2026, 10, 17)
    assert domain.today(ZoneInfo("UTC")) == date(2026, 10, 16)


def test_charity_only_mode_pays_nobody_from_anybody_elses_stake(monkeypatch):
    monkeypatch.setattr(domain, "PAYOUT_CAP_X", 0)  # PAYOUT_CAP_X=0 in the environment
    d, fee, charity = settle([pact(1, 50_000, 4, 0), pact(2, 10_000, 3, 3)])
    assert d == {1: -200_000, 2: 0} and fee == 24_000 and charity == 176_000  # the winner is paid nothing; everything after the fee goes to charity


def test_winners_who_staked_nothing_do_not_divide_by_zero():
    d, fee, charity = settle([pact(1, 0, 3, 3), pact(2, 50_000, 3, 0)])
    assert d[1] == 0 and sum(d.values()) + fee + charity == 0
