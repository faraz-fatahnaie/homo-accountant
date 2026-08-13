"""Unit tests: exact money handling (integer rials, toman conversion)."""

from __future__ import annotations

import pytest

from app.core.money import is_balanced, rial_to_toman_exact, rials, toman_to_rial


class TestRials:
    def test_construct(self) -> None:
        assert rials(1_000_000) == 1_000_000
        assert rials(0) == 0

    def test_rejects_float(self) -> None:
        with pytest.raises(TypeError):
            rials(10.5)  # type: ignore[arg-type]

    def test_rejects_bool(self) -> None:
        with pytest.raises(TypeError):
            rials(True)  # type: ignore[arg-type]

    def test_rejects_string(self) -> None:
        with pytest.raises(TypeError):
            rials("1000")  # type: ignore[arg-type]


class TestTomanConversion:
    def test_exact(self) -> None:
        assert toman_to_rial(4_850_000) == 48_500_000
        assert toman_to_rial(1) == 10
        assert toman_to_rial(0) == 0

    def test_negative(self) -> None:
        assert toman_to_rial(-5) == -50

    def test_large_values_no_overflow(self) -> None:
        assert toman_to_rial(10**15) == 10**16

    def test_rial_to_toman_lossless(self) -> None:
        assert rial_to_toman_exact(48_500_000) == (4_850_000, 0)
        assert rial_to_toman_exact(47) == (4, 7)  # remainder kept, nothing lost

    def test_rejects_float_input(self) -> None:
        with pytest.raises(TypeError):
            toman_to_rial(10.0)  # type: ignore[arg-type]


class TestBalance:
    def test_balanced(self) -> None:
        assert is_balanced(100, 100)

    def test_unbalanced(self) -> None:
        assert not is_balanced(100, 99)
        assert not is_balanced(0, 0)
        assert not is_balanced(0, 100)
