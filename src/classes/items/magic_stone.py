from operator import index as _as_integer
from typing import Union


class MagicStone(int):
    """
    灵石，实际上是一个int类，代表持有的灵石的数量。

    An immutable amount, like the ``int`` it is. There is exactly one number
    here: the ``int`` value itself. ``.value`` is a read-only view of it, kept
    because the save layer and the UI address the amount by that name.

    Every additive path returns a *new* ``MagicStone``, so ``+=`` rebinds the
    holder's attribute instead of mutating an object other holders may alias.

    An amount of stones is integral. Operands are converted with
    ``operator.index``, which accepts ``int`` and ``MagicStone`` and rejects a
    string or a float outright rather than parsing ``"10"`` or silently
    truncating ``1.9``; a wallet is not a place to discover a rounding rule.
    """

    __slots__ = ()

    def __new__(cls, value: Union['MagicStone', int]) -> 'MagicStone':
        return super().__new__(cls, _as_integer(value))

    @property
    def value(self) -> int:
        """The amount, derived from this object rather than stored beside it."""
        return int(self)

    def __str__(self) -> str:
        from src.i18n import t
        return t("{value} Spirit Stones", value=int(self))

    def __repr__(self) -> str:
        return f"MagicStone({int(self)})"

    def get_info(self) -> str:
        return str(self)

    def get_detailed_info(self) -> str:
        return str(self)

    def __add__(self, other: Union['MagicStone', int]) -> 'MagicStone':
        return MagicStone(int(self) + _as_integer(other))

    def __radd__(self, other: Union['MagicStone', int]) -> 'MagicStone':
        return MagicStone(_as_integer(other) + int(self))

    def __sub__(self, other: Union['MagicStone', int]) -> 'MagicStone':
        return MagicStone(int(self) - _as_integer(other))

    def __rsub__(self, other: Union['MagicStone', int]) -> 'MagicStone':
        return MagicStone(_as_integer(other) - int(self))
