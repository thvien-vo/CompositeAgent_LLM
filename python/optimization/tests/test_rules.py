import itertools

import numpy as np
import pytest

from optimization.rules import (PLY, STACK, RepairError, Repairer, Rules, check_rules, full_laminate, notation,
                                satisfies)

R = Rules()


def sym(half):
    return list(half) + list(half[::-1])


def test_symmetry_rule():
    assert check_rules(sym([0, 1, 2, 3]), R)["symmetric"]
    assert not check_rules([0, 1, 2, 3, 3, 1, 2, 0], R)["symmetric"]


def test_balance_rule():
    assert check_rules(sym([0, 1, 2, 3]), R)["balanced"]
    assert not check_rules(sym([0, 1, 1, 3]), R)["balanced"]


def test_ten_percent_rule():
    # 20 plies: each family needs >= 2 plies
    ok = sym([0, 1, 2, 3, 0, 0, 0, 3, 1, 2])
    assert check_rules(ok, R)["min_fraction"]
    no90 = sym([0, 1, 2, 0, 0, 0, 0, 0, 1, 2])
    assert not check_rules(no90, R)["min_fraction"]
    assert R.required_family_plies(20) == 2 and R.required_family_plies(22) == 3 and R.required_family_plies(8) == 1


def test_contiguity_rule_counts_across_midplane():
    assert check_rules(sym([0, 1, 2, 3, 0, 0]), R)["contiguity"]          # 4 zeros at the mid-plane: ok
    assert not check_rules(sym([1, 2, 3, 0, 0, 0]), R)["contiguity"]      # 6 zeros at the mid-plane
    assert not check_rules(sym([0, 0, 0, 0, 0, 1, 2, 3]), R)["contiguity"]  # 5 zeros on the outside
    assert check_rules(sym([0, 0, 0, 0, 3, 1, 2, 3]), R)["contiguity"]


def test_rules_can_be_switched_off():
    off = Rules(symmetric=False, balanced=False, min_fraction=None, max_contiguous=None)
    assert check_rules([0, 0, 0, 0, 0, 0, 1, 1], off) == {"ply_count": True}


def test_allowed_ply_counts():
    assert R.allowed_ply_counts(PLY) == list(range(8, 66, 2))
    # stacks: the half laminate needs one 0_2, one +-45 and one 90_2 stack (10 % rule) -> at least 12 plies
    assert R.allowed_ply_counts(STACK) == list(range(12, 68, 4))
    assert Rules(symmetric=False).allowed_ply_counts(PLY) == list(range(8, 65))


def test_stack_decode():
    g = np.array([[-1, 0, 1, 2]], dtype=np.int8)
    assert STACK.decode(g).tolist() == [[-1, -1, 0, 0, 1, 2, 3, 3]]


COMBOS = [Rules(), Rules(symmetric=False), Rules(balanced=False), Rules(min_fraction=None),
          Rules(max_contiguous=None), Rules(symmetric=False, balanced=False), Rules(n_min=8, n_max=16),
          Rules(max_contiguous=2), Rules(min_fraction=0.2), Rules(n_min=24, n_max=40)]


@pytest.mark.parametrize("enc", [PLY, STACK])
@pytest.mark.parametrize("rules", COMBOS)
def test_repair_always_returns_valid_designs(enc, rules, rng):
    if enc is STACK and rules.max_contiguous == 2:
        with pytest.raises(ValueError):
            Repairer(enc, rules)
        return
    rep = Repairer(enc, rules)
    for i in range(1500):
        g = rng.integers(-1, enc.n_symbols, size=rep.n_genes).astype(np.int8)
        if i % 4 == 0:
            g[:] = rng.integers(0, enc.n_symbols)  # worst case: one symbol everywhere
        out = rep.repair(g, rng)
        full = full_laminate(enc.decode(out[None]), rules.symmetric)[0]
        assert satisfies(full, rules), (g, out)
        assert len(full) in rules.allowed_ply_counts(enc)


def test_repair_keeps_valid_designs_unchanged(rng):
    rep = Repairer(PLY, R)
    for _ in range(300):
        v = rep.random_valid(rng)
        assert np.array_equal(rep.repair(v, rng), v)


def test_notation():
    assert notation(sym([1, 2, 0, 0, 3]), True) == "[45/-45/0_2/90]s"
