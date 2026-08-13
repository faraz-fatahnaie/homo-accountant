"""Exact money handling — integer Iranian rials only. Never use float.

All ledger amounts are `Rials` (an int). Conversions between toman and rial are
exact: 1 toman = 10 rials. No rounding is ever applied to stored amounts.
"""

from __future__ import annotations

from typing import NewType

Rials = NewType("Rials", int)


def rials(value: int) -> Rials:
    """Construct a Rials amount; rejects non-integers (incl. bools/floats)."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("rial amount must be an integer")
    return Rials(value)


def toman_to_rial(toman: int) -> Rials:
    """Exact conversion: 1 toman = 10 rials (integer input required)."""
    if not isinstance(toman, int) or isinstance(toman, bool):
        raise TypeError("toman amount must be an integer")
    return Rials(toman * 10)


def rial_to_toman_exact(amount: Rials) -> tuple[int, int]:
    """Split a rial amount into (whole_toman, remainder_rials) — lossless."""
    return int(amount) // 10, int(amount) % 10


def is_balanced(debits: int, credits: int) -> bool:
    return debits == credits and debits > 0
