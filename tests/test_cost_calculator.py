from __future__ import annotations

import pytest

from gatekeeper.metrics import CostLedger, PricingModel, render_finops_table


def _four_scenario_ledger() -> CostLedger:
    ledger = CostLedger(PricingModel())
    for i in range(5):
        ledger.record(f"a{i}", outcome="blocked", local_calls=0, cloud_calls=0)
    for i in range(8):
        ledger.record(f"b{i}", outcome="local", local_calls=1, cloud_calls=0)
    for i in range(4):
        ledger.record(f"c{i}", outcome="cloud", local_calls=1, cloud_calls=1)
    for i in range(3):
        ledger.record(f"d{i}", outcome="abstain", local_calls=1, cloud_calls=1)
    return ledger


def test_four_scenario_mix() -> None:
    s = _four_scenario_ledger().summary()
    assert (s.blocked_at_gate, s.solved_local, s.solved_cloud, s.abstained) == (5, 8, 4, 3)
    assert s.baseline_usd == pytest.approx(0.30)
    assert s.actual_usd == pytest.approx(8 * 0.0002 + 7 * 0.0152)
    assert s.actual_cloud_calls == 7
    assert s.cloud_calls_saved_pct == 65.0
    assert s.baseline_per_10k_usd == 150.0
    assert s.actual_per_10k_usd == 54.0
    assert s.saved_per_10k_usd == 96.0
    assert s.gate_tokens_spent == 0


def test_empty_ledger() -> None:
    s = CostLedger().summary()
    assert s.documents == 0
    assert s.cloud_calls_saved_pct == 0.0
    assert s.saved_per_10k_usd == 0.0


def test_escalating_everything_costs_more_than_baseline() -> None:
    ledger = CostLedger()
    ledger.record("x", outcome="cloud", local_calls=1, cloud_calls=1)
    assert ledger.summary().saved_usd < 0


def test_pricing_from_env() -> None:
    pricing = PricingModel.from_env(
        {"GATEKEEPER_PRICE_CLOUD_PER_CALL": "0.03", "GATEKEEPER_PRICE_LOCAL_PER_CALL": ""}
    )
    assert pricing.cloud_per_call == 0.03
    assert pricing.local_per_call == PricingModel().local_per_call
    with pytest.raises(ValueError):
        PricingModel.from_env({"GATEKEEPER_PRICE_CLOUD_PER_CALL": "-1"})


def test_table_contains_headline_metrics() -> None:
    ledger = _four_scenario_ledger()
    table = render_finops_table(ledger.summary(), ledger.pricing)
    assert "Total % cloud calls saved" in table
    assert "65.0%" in table
    assert "Estimated $ saved per 10,000 docs" in table
    assert "$96.00" in table
