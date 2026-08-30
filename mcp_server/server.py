import json
import sys
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp.server.mcpserver import MCPServer
from schemas.trade_intent import TradeIntent
from data.market_fetcher import MarketDataFetcher
from analysis.regime_detector import RegimeDetector
from agent.strategy_agent import StrategyAgent
from risk.risk_gate import RiskGate
from execution.alpaca_executor import AlpacaExecutor
from execution.position_monitor import PositionMonitor
from scheduler.autonomous_runner import AutonomousRunner

# Initialize MCP Server
mcp_server = MCPServer("alpaca-regime-options-agent")

# Initialize Pipeline Components
fetcher = MarketDataFetcher()
detector = RegimeDetector()
agent = StrategyAgent()
gate = RiskGate(max_position_size_pct=0.05)
executor = AlpacaExecutor()
monitor = PositionMonitor(profit_target_pct=0.50, stop_loss_pct=0.40)


@mcp_server.tool()
def detect_market_regime(symbol: str) -> str:
    """
    Fetch market data and classify the current market regime (BULLISH_TRENDING,
    BEARISH_TRENDING, HIGH_VOLATILITY, LOW_VOLATILITY, SIDEWAYS_CONSOLIDATION)
    along with technical indicators (SMA 20/50, RSI 14, ATR 14, Realized Volatility).
    """
    try:
        bars = fetcher.get_daily_bars(symbol.strip().upper(), days=60)
        analysis = detector.analyze(symbol.strip().upper(), bars)
        return json.dumps(analysis.summary_dict, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to detect regime for {symbol}: {str(e)}"})


@mcp_server.tool()
def get_account_risk_summary() -> str:
    """
    Retrieve Alpaca live account equity, buying power, cash, and active position metrics.
    """
    try:
        account = gate.get_account()
        positions = monitor.get_open_positions()
        return json.dumps({
            "status": "ONLINE",
            "account_status": str(account.status),
            "equity": float(account.equity),
            "buying_power": float(account.buying_power),
            "cash": float(account.cash),
            "open_positions_count": len(positions),
            "max_allowed_per_position_usd": float(account.equity) * 0.05,
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "OFFLINE / SIMULATION",
            "simulated_equity": 100000.0,
            "simulated_buying_power": 200000.0,
            "max_allowed_per_position_usd": 5000.0,
            "note": f"Live account unreachable ({str(e)}). Running in deterministic sandbox.",
        }, indent=2)


@mcp_server.tool()
def evaluate_risk_gate(trade_intent_json: str) -> str:
    """
    Run 100% deterministic mathematical Risk Gate verification on an AI TradeIntent proposal.
    Enforces max 5% position allocation, buying power limits, stop-loss sanity, and defined-risk options.
    """
    try:
        intent = TradeIntent.model_validate_json(trade_intent_json)
        result = gate.evaluate(intent)
        return json.dumps(result.model_dump(mode="json"), indent=2)
    except Exception as e:
        return json.dumps({"is_approved": False, "error": str(e)}, indent=2)


@mcp_server.tool()
def generate_ai_strategy(symbol: str) -> str:
    """
    Analyze market regime for a ticker and prompt Google Gemini to formulate
    a validated TradeIntent proposal adhering to strict regime strategy mapping.
    """
    try:
        bars = fetcher.get_daily_bars(symbol.strip().upper(), days=60)
        analysis = detector.analyze(symbol.strip().upper(), bars)
        intent = agent.generate_trade_intent(analysis.summary_dict)
        return json.dumps(intent.model_dump(mode="json"), indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to generate strategy: {str(e)}"}, indent=2)


@mcp_server.tool()
def execute_alpaca_order(trade_intent_json: str, dry_run: bool = True) -> str:
    """
    Execute a cleared TradeIntent order on Alpaca (Paper/Live API) with OCC Option symbol formatting.
    """
    try:
        intent = TradeIntent.model_validate_json(trade_intent_json)
        # First verify Risk Gate
        risk_check = gate.evaluate(intent)
        if not risk_check.is_approved:
            return json.dumps({
                "success": False,
                "rejection_reasons": risk_check.rejection_reasons,
                "message": "Order blocked by Deterministic Hard Risk Gate.",
            }, indent=2)

        receipt = executor.execute_intent(intent, dry_run=dry_run)
        return json.dumps(receipt, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp_server.tool()
def monitor_and_liquidate_positions(dry_run: bool = True) -> str:
    """
    Scan all open positions in Alpaca, calculate unrealized P&L %,
    and execute auto-liquidation for positions hitting +50% Profit Target or -40% Stop Loss.
    """
    try:
        results = monitor.process_exits(dry_run=dry_run)
        return json.dumps(results, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp_server.tool()
def run_autonomous_pipeline(
    watchlist_csv: str = "SPY,AAPL,NVDA,QQQ,MSFT",
    max_positions: int = 5,
    dry_run: bool = True,
) -> str:
    """
    Execute a complete autonomous scan cycle across the specified watchlist symbols.
    """
    watchlist = [s.strip().upper() for s in watchlist_csv.split(",") if s.strip()]
    runner = AutonomousRunner(
        watchlist=watchlist,
        max_open_positions=max_positions,
        dry_run=dry_run,
        fetcher=fetcher,
        detector=detector,
        agent=agent,
        gate=gate,
        executor=executor,
        monitor=monitor,
    )
    report = runner.run_iteration()
    return json.dumps(report, indent=2)


def run_mcp_server():
    """Run the MCP server over stdio."""
    mcp_server.run()


if __name__ == "__main__":
    run_mcp_server()
