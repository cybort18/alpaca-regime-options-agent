import argparse
import json
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.market_fetcher import MarketDataFetcher
from analysis.regime_detector import RegimeDetector
from agent.strategy_agent import StrategyAgent
from risk.risk_gate import RiskGate
from execution.alpaca_executor import AlpacaExecutor
from execution.position_monitor import PositionMonitor
from scheduler.autonomous_runner import AutonomousRunner
from mcp_server.server import (
    run_mcp_server,
    detect_market_regime,
    get_account_risk_summary,
    evaluate_risk_gate,
    generate_ai_strategy,
    monitor_and_liquidate_positions,
    run_autonomous_pipeline,
)


def cmd_regime(args):
    """Detect market regime and print technical indicators for a symbol."""
    symbol = args.symbol.strip().upper()
    print(f"\n[CLI] Analyzing Market Regime for: {symbol}")
    fetcher = MarketDataFetcher()
    detector = RegimeDetector()
    bars = fetcher.get_daily_bars(symbol, days=args.days)
    analysis = detector.analyze(symbol, bars)
    print(json.dumps(analysis.summary_dict, indent=2))


def cmd_strategy(args):
    """Generate Gemini AI quantitative strategy proposal for a symbol."""
    symbol = args.symbol.strip().upper()
    print(f"\n[CLI] Formulating AI Strategy Proposal for: {symbol}")
    fetcher = MarketDataFetcher()
    detector = RegimeDetector()
    agent = StrategyAgent(model_name=args.model)
    bars = fetcher.get_daily_bars(symbol, days=60)
    analysis = detector.analyze(symbol, bars)
    intent = agent.generate_trade_intent(analysis.summary_dict)
    print(json.dumps(intent.model_dump(mode="json"), indent=2))


def cmd_scan(args):
    """Run an autonomous scan cycle across watchlist symbols."""
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    dry_run = not args.live
    print(f"\n[CLI] Triggering Autonomous Scan Cycle")
    print(f"Watchlist: {symbols} | Max Positions: {args.max_pos} | Mode: {'LIVE PAPER' if not dry_run else 'DRY-RUN SIMULATION'}")
    
    runner = AutonomousRunner(
        watchlist=symbols,
        max_open_positions=args.max_pos,
        dry_run=dry_run,
    )
    report = runner.run_iteration()
    print("\n[CLI] Cycle Summary Report:")
    print(json.dumps(report, indent=2))


def cmd_positions(args):
    """Inspect all open positions and evaluate profit-target / stop-loss exits."""
    print(f"\n[CLI] Fetching and Evaluating Active Positions...")
    monitor = PositionMonitor(profit_target_pct=args.profit_target, stop_loss_pct=args.stop_loss)
    results = monitor.process_exits(dry_run=not args.execute_close)
    print(json.dumps(results, indent=2))


def cmd_test(args):
    """Execute the full test suite."""
    print("\n[CLI] Running Complete Automated Test Suite...")
    import subprocess
    scripts = ["test_modules.py", "test_market_analysis.py", "test_pipeline_e2e.py", "test_runner.py"]
    for s in scripts:
        print(f"\n--- Executing {s} ---")
        res = subprocess.run([sys.executable, s], capture_output=False)
        if res.returncode != 0:
            print(f"[FAIL] {s} exited with code {res.returncode}")
            sys.exit(res.returncode)
    print("\n[PASS] All test suites completed successfully!")


def cmd_mcp(args):
    """Launch or test the MCP tool server."""
    if args.test:
        print("\n[CLI] Testing MCP Server Tools Integration...")
        print("\n1. Testing 'detect_market_regime' tool on SPY:")
        regime_out = detect_market_regime("SPY")
        print(regime_out)

        print("\n2. Testing 'get_account_risk_summary' tool:")
        risk_out = get_account_risk_summary()
        print(risk_out)

        print("\n3. Testing 'generate_ai_strategy' tool on SPY:")
        strat_out = generate_ai_strategy("SPY")
        print(strat_out)

        print("\n4. Testing 'evaluate_risk_gate' tool:")
        eval_out = evaluate_risk_gate(strat_out)
        print(eval_out)

        print("\n5. Testing 'monitor_and_liquidate_positions' tool:")
        mon_out = monitor_and_liquidate_positions(dry_run=True)
        print(mon_out)

        print("\n[PASS] All MCP Tools verified successfully!")
        return

    print("\n[CLI] Starting Alpaca Agent MCP Server (stdio transport)...")
    print("      Listening for JSON-RPC MCP requests from client (Press Ctrl+C to stop)...")
    try:
        run_mcp_server()
    except KeyboardInterrupt:
        print("\n[CLI] MCP Server stopped gracefully.")


def main():
    parser = argparse.ArgumentParser(
        description="Alpaca Regime-Aware Options & Equity Autonomous Trading Agent CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: scan
    p_scan = subparsers.add_parser("scan", help="Run autonomous scan cycle across watchlist")
    p_scan.add_argument("--symbols", default="SPY,AAPL,NVDA,QQQ,MSFT", help="Comma-separated ticker watchlist")
    p_scan.add_argument("--max-pos", type=int, default=5, help="Maximum concurrent positions")
    p_scan.add_argument("--live", action="store_true", help="Execute live paper orders (disables dry-run)")
    p_scan.set_defaults(func=cmd_scan)

    # Command: regime
    p_regime = subparsers.add_parser("regime", help="Analyze market regime for a ticker")
    p_regime.add_argument("symbol", help="Ticker symbol (e.g. SPY, AAPL)")
    p_regime.add_argument("--days", type=int, default=60, help="Number of historical daily bars")
    p_regime.set_defaults(func=cmd_regime)

    # Command: strategy
    p_strat = subparsers.add_parser("strategy", help="Generate AI trade proposal for a ticker")
    p_strat.add_argument("symbol", help="Ticker symbol (e.g. SPY, AAPL)")
    p_strat.add_argument("--model", default="gemini-2.5-flash", help="Gemini model name")
    p_strat.set_defaults(func=cmd_strategy)

    # Command: positions
    p_pos = subparsers.add_parser("positions", help="Inspect active positions and evaluate exit triggers")
    p_pos.add_argument("--profit-target", type=float, default=0.50, help="Profit target fraction (default 0.50 = 50%)")
    p_pos.add_argument("--stop-loss", type=float, default=0.40, help="Stop loss fraction (default 0.40 = 40%)")
    p_pos.add_argument("--execute-close", action="store_true", help="Execute live liquidation orders")
    p_pos.set_defaults(func=cmd_positions)

    # Command: test
    p_test = subparsers.add_parser("test", help="Run full automated test suites")
    p_test.set_defaults(func=cmd_test)

    # Command: mcp
    p_mcp = subparsers.add_parser("mcp", help="Start or test Model Context Protocol (MCP) server")
    p_mcp.add_argument("--test", action="store_true", help="Test and execute all registered MCP tools")
    p_mcp.set_defaults(func=cmd_mcp)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n[CLI] Process stopped by user.")


if __name__ == "__main__":
    main()
