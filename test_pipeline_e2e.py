import json
from dataclasses import dataclass
from data.market_fetcher import MarketDataFetcher
from analysis.regime_detector import RegimeDetector
from agent.strategy_agent import StrategyAgent
from risk.risk_gate import RiskGate
from execution.alpaca_executor import AlpacaExecutor
from schemas.trade_intent import TradeIntent, MarketRegime


@dataclass
class MockTradeAccount:
    """Mock Alpaca TradeAccount for local deterministic testing."""
    equity: float = 100_000.00
    buying_power: float = 200_000.00
    cash: float = 50_000.00
    status: str = "ACTIVE"
    trading_blocked: bool = False


def run_e2e_pipeline_tests():
    print("================================================================================")
    print("STARTING END-TO-END PIPELINE INTEGRATION TEST")
    print("Pipeline: Data Fetch -> Regime Detector -> Strategy Agent -> Risk Gate -> Executor")
    print("================================================================================")

    # Initialize Components
    fetcher = MarketDataFetcher()
    detector = RegimeDetector()
    agent = StrategyAgent()
    gate = RiskGate(max_position_size_pct=0.05)
    executor = AlpacaExecutor()
    mock_account = MockTradeAccount(equity=100_000.0)

    test_symbols = ["SPY", "AAPL", "NVDA"]

    for symbol in test_symbols:
        print(f"\n--------------------------------------------------------------------------------")
        print(f"Executing Complete Pipeline for Symbol: {symbol}")
        print(f"--------------------------------------------------------------------------------")

        # STEP 1: Market Data Fetching
        print(f"[Step 1] Fetching market data...")
        bars_df = fetcher.get_daily_bars(symbol, days=60)
        print(f"         Fetched {len(bars_df)} bars. Latest Close: ${bars_df['close'].iloc[-1]:.2f}")

        # STEP 2: Technical & Regime Detection
        print(f"[Step 2] Analyzing Technical Indicators & Market Regime...")
        analysis = detector.analyze(symbol, bars_df)
        print(f"         Detected Regime: {analysis.detected_regime.value}")
        print(f"         Confidence: {analysis.confidence:.2f} | RSI: {analysis.rsi_14:.1f} | Realized Vol: {analysis.realized_volatility:.1f}%")
        print(f"         Rationale: {analysis.summary_dict['rationale']}")

        # STEP 3: AI Strategy Proposal Formulation
        print(f"[Step 3] AI Strategy Agent formulating TradeIntent...")
        proposal = agent.generate_trade_intent(analysis.summary_dict)
        assert isinstance(proposal, TradeIntent)
        print(f"         Proposed Strategy: {proposal.strategy_name} ({proposal.instrument_type.value})")
        print(f"         Target: ${proposal.target_price:.2f} | Stop Loss: ${proposal.stop_loss:.2f}")
        if proposal.options_legs:
            print(f"         Options Legs ({len(proposal.options_legs)} legs):")
            for idx, leg in enumerate(proposal.options_legs, 1):
                print(f"           Leg {idx}: {leg.action.value} {leg.option_type.value} @ ${leg.strike_price} (Exp: {leg.expiration_date})")

        # STEP 4: Deterministic Hard Risk Gate Evaluation
        print(f"[Step 4] RiskGate evaluating proposal against Account rules (Max 5% equity)...")
        risk_result = gate.evaluate(proposal, account_override=mock_account)
        print(f"         Proposed Cost: ${risk_result.proposed_cost_usd:,.2f} | Max Allowed: ${risk_result.max_allowed_allocation_usd:,.2f}")
        print(f"         Approved by Risk Gate? -> {risk_result.is_approved}")

        assert risk_result.is_approved, f"Proposal failed risk check: {risk_result.rejection_reasons}"

        # STEP 5: Execution Engine (Dry Run / Paper Test)
        print(f"[Step 5] Alpaca Order Executor submitting order...")
        exec_receipt = executor.execute_intent(proposal, dry_run=True)
        print(f"         Execution Status: {exec_receipt.get('status')}")
        print(f"         Order ID: {exec_receipt.get('order_id')}")
        print(f"         Execution Details: {json.dumps(exec_receipt, indent=2)}")

        print(f"[SUCCESS] Symbol {symbol} successfully traversed complete pipeline!")

    print("\n================================================================================")
    print("ALL END-TO-END PIPELINE INTEGRATION TESTS PASSED 100% SUCCESSFULLY!")
    print("================================================================================")


if __name__ == "__main__":
    run_e2e_pipeline_tests()
