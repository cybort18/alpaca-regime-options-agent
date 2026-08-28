import json
from dataclasses import dataclass
from execution.position_monitor import PositionMonitor
from scheduler.autonomous_runner import AutonomousRunner


@dataclass
class MockPosition:
    """Mock Alpaca Position for local testing."""
    symbol: str
    qty: float
    avg_entry_price: float
    current_price: float
    unrealized_pl: float
    unrealized_plpc: float


@dataclass
class MockTradeAccount:
    """Mock Alpaca TradeAccount for local deterministic testing."""
    equity: float = 100_000.00
    buying_power: float = 200_000.00
    cash: float = 50_000.00
    status: str = "ACTIVE"
    trading_blocked: bool = False


def run_runner_tests():
    print("================================================================================")
    print("1. Testing PositionMonitor & Exit Decision Logic")
    print("================================================================================")

    monitor = PositionMonitor(profit_target_pct=0.50, stop_loss_pct=0.40)

    # Test Positions:
    # 1. AAPL: +55% profit (should trigger TAKE_PROFIT)
    # 2. TSLA: -45% loss (should trigger STOP_LOSS)
    # 3. SPY:  +12% gain (should HOLD)
    mock_positions = [
        MockPosition(
            symbol="AAPL",
            qty=10,
            avg_entry_price=200.0,
            current_price=310.0,
            unrealized_pl=1100.0,
            unrealized_plpc=0.55,
        ),
        MockPosition(
            symbol="TSLA",
            qty=5,
            avg_entry_price=250.0,
            current_price=137.5,
            unrealized_pl=-562.5,
            unrealized_plpc=-0.45,
        ),
        MockPosition(
            symbol="SPY",
            qty=5,
            avg_entry_price=550.0,
            current_price=616.0,
            unrealized_pl=330.0,
            unrealized_plpc=0.12,
        ),
    ]

    exit_results = monitor.process_exits(positions_override=mock_positions, dry_run=True)
    print(f"Evaluated {len(exit_results)} positions for exits:")
    for res in exit_results:
        print(f" - Symbol: {res['symbol']} | Action: {res['action']} | PnL: {res['unrealized_plpc']*100:+.1f}% | Reason: {res['reason']}")

    # Assertions on Exit Signals
    aapl_res = next(r for r in exit_results if r["symbol"] == "AAPL")
    tsla_res = next(r for r in exit_results if r["symbol"] == "TSLA")
    spy_res = next(r for r in exit_results if r["symbol"] == "SPY")

    assert aapl_res["action"] == "TAKE_PROFIT"
    assert tsla_res["action"] == "STOP_LOSS"
    assert spy_res["action"] == "HOLD"
    print("\n[PASS] PositionMonitor correctly identified TAKE_PROFIT, STOP_LOSS, and HOLD signals!")

    print("\n================================================================================")
    print("2. Testing AutonomousRunner Complete Cycle")
    print("================================================================================")

    runner = AutonomousRunner(
        watchlist=["SPY", "AAPL", "NVDA", "QQQ", "MSFT"],
        max_open_positions=4,
        scan_interval_seconds=10,
        dry_run=True,
        monitor=monitor,
    )

    mock_account = MockTradeAccount(equity=100_000.0, buying_power=200_000.0)

    # Run one full iteration cycle with mock existing positions
    cycle_report = runner.run_iteration(
        account_override=mock_account,
        positions_override=mock_positions,
    )

    print("\n================================================================================")
    print("AUTONOMOUS CYCLE REPORT SUMMARY:")
    print(json.dumps(cycle_report, indent=2))
    print("================================================================================")

    # Verification assertions:
    # 1. AAPL and TSLA should be liquidated.
    assert "AAPL" in cycle_report["liquidations_executed"]
    assert "TSLA" in cycle_report["liquidations_executed"]
    # 2. SPY should be actively held.
    assert "SPY" in cycle_report["actively_held_positions"]
    # 3. SPY should be skipped during watchlist scan (already held).
    assert any(s["symbol"] == "SPY" and s["reason"] == "already_active_position" for s in cycle_report["skipped_candidates"])
    # 4. New orders should be submitted for candidates without positions.
    assert len(cycle_report["new_orders_submitted"]) > 0

    print("\n[PASS] AutonomousRunner cycle passed all assertions!")
    print("================================================================================")
    print("ALL SECTION 4 TESTS PASSED WITH 100% SUCCESS!")
    print("================================================================================")


if __name__ == "__main__":
    run_runner_tests()
