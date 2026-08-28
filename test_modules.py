import json
from dataclasses import dataclass
from datetime import date, timedelta
from schemas.trade_intent import (
    InstrumentType,
    MarketRegime,
    OptionAction,
    OptionLeg,
    OptionType,
    OrderSide,
    TradeIntent,
)
from risk.risk_gate import RiskGate


@dataclass
class MockTradeAccount:
    """Mock Alpaca TradeAccount for local deterministic testing."""
    equity: float = 100_000.00
    buying_power: float = 200_000.00
    cash: float = 50_000.00
    status: str = "ACTIVE"
    trading_blocked: bool = False


def run_tests():
    print("==================================================")
    print("1. Testing TradeIntent Pydantic Schema Validation")
    print("==================================================")

    # Expiration date 30 days in the future
    exp_date = (date.today() + timedelta(days=30)).isoformat()

    # Scenario A: Valid Bull Call Spread Option Intent
    valid_option_proposal = TradeIntent(
        symbol="SPY",
        market_regime=MarketRegime.BULLISH_TRENDING,
        instrument_type=InstrumentType.OPTION,
        strategy_name="BULL_CALL_SPREAD",
        action=OrderSide.BUY,
        quantity=2,
        estimated_entry_price=3.50,
        target_price=590.0,
        stop_loss=2.00,
        options_legs=[
            OptionLeg(
                strike_price=580.0,
                expiration_date=exp_date,
                option_type=OptionType.CALL,
                action=OptionAction.BUY_TO_OPEN,
                quantity=2,
            ),
            OptionLeg(
                strike_price=590.0,
                expiration_date=exp_date,
                option_type=OptionType.CALL,
                action=OptionAction.SELL_TO_OPEN,
                quantity=2,
            ),
        ],
        reasoning="SPY breaks out of ascending triangle with high volume momentum in a bullish trending regime.",
        confidence_score=0.88,
    )
    print("[PASS] Valid Option Proposal Schema:")
    print(json.dumps(valid_option_proposal.model_dump(mode="json"), indent=2))

    # Scenario B: Valid Equity Long Proposal
    valid_equity_proposal = TradeIntent(
        symbol="AAPL",
        market_regime=MarketRegime.LOW_VOLATILITY,
        instrument_type=InstrumentType.EQUITY,
        strategy_name="EQUITY_BREAKOUT",
        action=OrderSide.BUY,
        quantity=10,
        estimated_entry_price=220.0,
        target_price=240.0,
        stop_loss=210.0,
        reasoning="Support held firmly at 200 EMA with compression squeeze.",
        confidence_score=0.79,
    )
    print("\n[PASS] Valid Equity Proposal Schema Created Successfully.")

    # Scenario C: Invalid Option Proposal (empty legs)
    try:
        TradeIntent(
            symbol="NVDA",
            market_regime=MarketRegime.HIGH_VOLATILITY,
            instrument_type=InstrumentType.OPTION,
            target_price=140.0,
            stop_loss=110.0,
            options_legs=[],
            reasoning="Testing invalid empty legs validation.",
        )
        raise AssertionError("Failed to catch empty options_legs!")
    except Exception as e:
        print(f"\n[PASS] Successfully caught empty options_legs error:\n       --> {e.errors()[0]['msg']}")

    # Scenario D: Invalid Naked Short Option (Defined risk violation)
    try:
        TradeIntent(
            symbol="TSLA",
            market_regime=MarketRegime.BEARISH_TRENDING,
            instrument_type=InstrumentType.OPTION,
            target_price=180.0,
            stop_loss=260.0,
            options_legs=[
                OptionLeg(
                    strike_price=250.0,
                    expiration_date=exp_date,
                    option_type=OptionType.CALL,
                    action=OptionAction.SELL_TO_OPEN,
                    quantity=1,
                )
            ],
            reasoning="Attempting naked call sell.",
        )
        raise AssertionError("Failed to catch naked short option!")
    except Exception as e:
        print(f"\n[PASS] Successfully blocked Naked Short Option (Defined Risk rule):\n       --> {e.errors()[0]['msg']}")

    print("\n==================================================")
    print("2. Testing Deterministic RiskGate Rules")
    print("==================================================")

    gate = RiskGate(max_position_size_pct=0.05)
    mock_account = MockTradeAccount(equity=100_000.0, buying_power=200_000.0)

    print(f"Mock Account: Equity=${mock_account.equity:,.2f} | Max 5% Allocation=${mock_account.equity * 0.05:,.2f}")

    # Test 1: Valid Equity Allocation ($2,200 is <= $5,000 max allowed)
    res_equity = gate.evaluate(valid_equity_proposal, account_override=mock_account)
    print(f"\n- Test 1 (Valid AAPL Equity $2,200): Approved={res_equity.is_approved}, Proposed=${res_equity.proposed_cost_usd:,.2f}")
    assert res_equity.is_approved, f"Expected approved, got {res_equity.rejection_reasons}"

    # Test 2: Valid Option Spread Allocation ($700 is <= $5,000 max allowed)
    res_option = gate.evaluate(valid_option_proposal, account_override=mock_account)
    print(f"- Test 2 (Valid SPY Bull Call Spread $700): Approved={res_option.is_approved}, Proposed=${res_option.proposed_cost_usd:,.2f}")
    assert res_option.is_approved, f"Expected approved, got {res_option.rejection_reasons}"

    # Test 3: Oversized Order ($22,000 proposed > $5,000 max allowed 5% limit)
    oversized_proposal = TradeIntent(
        symbol="AAPL",
        market_regime=MarketRegime.BULLISH_TRENDING,
        instrument_type=InstrumentType.EQUITY,
        action=OrderSide.BUY,
        quantity=100,
        estimated_entry_price=220.0,  # $22,000
        target_price=250.0,
        stop_loss=210.0,
        reasoning="Testing max 5% position size limit.",
    )
    res_oversized = gate.evaluate(oversized_proposal, account_override=mock_account)
    print(f"- Test 3 (Oversized Order $22,000): Approved={res_oversized.is_approved}")
    print(f"  Rejection Reason: {res_oversized.rejection_reasons[0]}")
    assert not res_oversized.is_approved

    # Test 4: Bad Stop-Loss Check (Stop loss higher than entry price on BUY)
    bad_stop_proposal = TradeIntent(
        symbol="MSFT",
        market_regime=MarketRegime.SIDEWAYS_CONSOLIDATION,
        instrument_type=InstrumentType.EQUITY,
        action=OrderSide.BUY,
        quantity=5,
        estimated_entry_price=400.0,
        target_price=450.0,
        stop_loss=415.0,  # Invalid for BUY
        reasoning="Testing stop loss sanity check.",
    )
    res_bad_stop = gate.evaluate(bad_stop_proposal, account_override=mock_account)
    print(f"- Test 4 (Bad Stop Loss for BUY): Approved={res_bad_stop.is_approved}")
    print(f"  Rejection Reason: {res_bad_stop.rejection_reasons[0]}")
    assert not res_bad_stop.is_approved

    # Test 5: Inactive or Blocked Account
    blocked_account = MockTradeAccount(equity=100_000.0, trading_blocked=True)
    res_blocked = gate.evaluate(valid_equity_proposal, account_override=blocked_account)
    print(f"- Test 5 (Trading Blocked Account): Approved={res_blocked.is_approved}")
    print(f"  Rejection Reason: {res_blocked.rejection_reasons[0]}")
    assert not res_blocked.is_approved

    print("\n==================================================")
    print("ALL TESTS PASSED WITH 100% DETERMINISTIC SUCCESS!")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
