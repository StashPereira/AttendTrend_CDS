import pytest
from app.services.attendance import percentage, recovery, scenario


@pytest.mark.parametrize(
    "a,c,expected", [(0, 0, None), (0, 10, 0), (10, 10, 100), (3, 4, 75), (1, 3, 33.33)]
)
def test_percentages(a, c, expected):
    assert percentage(a, c) == expected


def test_recovery_exact_and_impossible():
    exact = recovery(3, 4, 8, 75)
    assert exact["required_consecutive"] == 0
    assert exact["safe_to_skip"] == 0
    assert exact["required_of_remaining"] == 6
    assert exact["maximum_final_absences"] == 2
    bad = recovery(0, 10, 2, 75)
    assert bad["required_consecutive"] == 30
    assert not bad["recoverable"]
    assert bad["safe_to_skip"] == 0


def test_target_one_hundred():
    assert recovery(9, 10, 100, 100)["required_consecutive"] is None
    assert not recovery(9, 10, 100, 100)["recoverable"]
    assert recovery(10, 10, 10, 100)["required_consecutive"] == 0


def test_safe_skip_and_rounding():
    assert recovery(8, 10, 10, 75)["safe_to_skip"] == 0
    assert recovery(9, 10, 10, 75)["safe_to_skip"] == 2
    assert recovery(9, 10, 1, 75)["safe_to_skip"] == 1
    assert recovery(0, 0, 0, 75)["best_case"] is None
    assert recovery(1, 3, 5, 66.67)["required_consecutive"] == 4


def test_what_if():
    assert scenario(3, 4, 1, 0, 75)["projected"] == 80
    assert not scenario(3, 4, 0, 1, 75)["meets_target"]
    assert scenario(0, 0, 0, 0, 75)["projected"] is None


@pytest.mark.parametrize("target", [50, 66.67, 75, 80, 99.99, 100])
def test_recovery_matches_bruteforce(target):
    for c in range(12):
        for a in range(c + 1):
            result = recovery(a, c, 20, target)
            feasible = [n for n in range(21) if (a + n) * 100 >= target * (c + 20)]
            assert result["recoverable"] == bool(feasible)
            if feasible:
                assert result["required_of_remaining"] == feasible[0]
            safe = [n for n in range(21) if c + n and a * 100 >= target * (c + n)]
            assert result["safe_to_skip"] == (max(safe) if safe else 0)
