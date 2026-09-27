from datetime import date

from main import settle, week_start

# Loser misses 2 days at 50k -> pool 100k, fee 12k, winners split 88k by stake (1:3)
deltas, fee, charity = settle([
    {"id": 1, "stake": 50_000, "target_days": 4, "done_days": 2},
    {"id": 2, "stake": 10_000, "target_days": 3, "done_days": 3},
    {"id": 3, "stake": 30_000, "target_days": 5, "done_days": 6},
])
assert deltas == {1: -100_000, 2: 22_000, 3: 66_000}, deltas
assert (fee, charity) == (12_000, 0)

# Nobody wins -> everything after fee goes to charity, money is conserved
deltas, fee, charity = settle([{"id": 1, "stake": 20_000, "target_days": 2, "done_days": 1}])
assert deltas == {1: -20_000} and fee + charity == 20_000

assert week_start(date(2026, 9, 23)) == date(2026, 9, 19)  # Wed -> previous Saturday
assert week_start(date(2026, 9, 19)) == date(2026, 9, 19)
print("ok")
