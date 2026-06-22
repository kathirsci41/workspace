"""
Configurable tolerance for verification amount checks.
Replaces the hard-coded abs(left - right) <= 2 in order_bundle_verifier.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToleranceConfig:
    """
    Amount match tolerance.
    PASSES when: abs(left - right) <= max(absolute_floor, percentage * max(|left|, |right|, 1)).
    Defaults: 2% tolerance, ₹5 absolute floor.
    """
    percentage: float = 0.02
    absolute_floor: float = 5.0
    per_field: dict[str, float] = field(default_factory=dict)

    def passes(self, left: float, right: float, field_name: str = "") -> bool:
        pct = self.per_field.get(field_name, self.percentage)
        threshold = max(self.absolute_floor, pct * max(abs(left), abs(right), 1.0))
        return abs(left - right) <= threshold

    def diff_pct(self, left: float, right: float) -> float:
        denom = max(abs(left), abs(right), 1.0)
        return abs(left - right) / denom * 100


DEFAULT_TOLERANCE = ToleranceConfig()


def demo() -> None:
    t = ToleranceConfig()
    assert t.passes(1000, 1000)          # exact
    assert t.passes(1000, 1015)          # within 2% (20) → pass
    assert not t.passes(1000, 1025)      # 25 > 20 → fail
    assert t.passes(100, 102)            # within ₹5 floor
    assert not t.passes(696200, 554600)  # large partial-billing gap stays flagged
    assert round(t.diff_pct(1000, 1100), 1) == 9.1
    print("tolerance_config demo OK")


if __name__ == "__main__":
    demo()
