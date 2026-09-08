"""A spirit-stone wallet holds one number, and holds it immutably.

`MagicStone` used to carry a second amount in `.value` that its in-place
operators updated while the `int` base stayed frozen, so the same wallet could
answer two different numbers depending on how it was read, and a `+=` mutated
an object other holders might alias. These tests pin the single truth and the
value semantics; they add no new arithmetic rule and no clamping.
"""

from __future__ import annotations

import copy
import json

import pytest

from src.classes.items.magic_stone import MagicStone


def test_value_and_int_are_the_same_number():
    wallet = MagicStone(100)
    assert wallet.value == 100
    assert int(wallet) == 100
    assert int.__int__(wallet) == 100


def test_value_is_read_only():
    wallet = MagicStone(100)
    with pytest.raises(AttributeError):
        wallet.value = 999
    assert wallet.value == 100


def test_in_place_addition_rebinds_and_never_mutates_an_alias():
    wallet = MagicStone(100)
    alias = wallet

    wallet += 50

    assert wallet.value == 150
    assert int(wallet) == 150
    # The other holder still sees exactly what it held.
    assert alias.value == 100
    assert int(alias) == 100
    assert wallet is not alias


def test_in_place_subtraction_rebinds_and_never_mutates_an_alias():
    wallet = MagicStone(100)
    alias = wallet

    wallet -= 30

    assert wallet.value == 70
    assert alias.value == 100
    assert wallet is not alias


def test_additive_paths_accept_a_magic_stone_on_either_side():
    left = MagicStone(100)
    right = MagicStone(25)

    assert (left + right).value == 125
    assert (left - right).value == 75
    assert (left + 25).value == 125
    assert (left - 25).value == 75
    # int on the left still yields a wallet, not a bare int.
    assert (25 + left).value == 125
    assert (125 - left).value == 25
    for result in (left + right, left - right, 25 + left, 125 - left):
        assert isinstance(result, MagicStone)


def test_in_place_operators_accept_a_magic_stone_operand():
    wallet = MagicStone(100)
    wallet += MagicStone(10)
    wallet -= MagicStone(5)

    assert wallet.value == 105
    assert isinstance(wallet, MagicStone)


@pytest.mark.parametrize("unsupported", [1.9, 2.0, "10", None])
def test_non_integral_operands_are_rejected_rather_than_coerced(unsupported):
    """A wallet is not where a parsing or rounding rule gets invented."""
    wallet = MagicStone(100)

    with pytest.raises(TypeError):
        wallet + unsupported
    with pytest.raises(TypeError):
        wallet - unsupported
    with pytest.raises(TypeError):
        MagicStone(unsupported)
    assert wallet.value == 100


def test_integral_operands_are_preserved_exactly():
    wallet = MagicStone(100)

    assert (wallet + 7).value == 107
    assert (wallet + MagicStone(7)).value == 107
    assert (wallet + True).value == 101
    assert MagicStone(MagicStone(9)).value == 9


def test_zero_and_negative_amounts_are_preserved_without_new_clamping():
    assert MagicStone(0).value == 0
    assert not MagicStone(0)
    assert bool(MagicStone(1))

    # Spending more than is held stays negative; this layer invents no floor.
    wallet = MagicStone(10)
    wallet -= 30
    assert wallet.value == -20
    assert int(wallet) == -20
    assert MagicStone(-5).value == -5


def test_comparisons_work_against_ints_and_other_wallets():
    wallet = MagicStone(100)

    assert wallet == 100
    assert wallet == MagicStone(100)
    assert wallet > MagicStone(99)
    assert wallet < 101
    assert wallet >= 100
    assert sorted([MagicStone(3), MagicStone(1), MagicStone(2)]) == [1, 2, 3]
    assert hash(wallet) == hash(100)


def test_it_serializes_as_a_plain_number():
    wallet = MagicStone(42)

    assert json.dumps({"magic_stone": wallet}) == '{"magic_stone": 42}'
    # The save layer addresses the amount by name; it must be the same number.
    assert json.dumps({"magic_stone": wallet.value}) == '{"magic_stone": 42}'


def test_copies_keep_the_amount():
    wallet = MagicStone(77)

    assert copy.copy(wallet).value == 77
    assert copy.deepcopy(wallet).value == 77
    assert copy.deepcopy({"w": wallet})["w"].value == 77


def test_presentation_stays_prose_and_is_never_the_number():
    wallet = MagicStone(42)

    assert wallet.get_info() == str(wallet)
    assert wallet.get_detailed_info() == str(wallet)
    assert str(wallet) != "42"
    assert "42" in repr(wallet)
