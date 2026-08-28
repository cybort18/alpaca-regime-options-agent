import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from data.market_fetcher import MarketDataFetcher
from analysis.regime_detector import RegimeDetector
from agent.strategy_agent import StrategyAgent
from risk.risk_gate import RiskGate
from execution.alpaca_executor import AlpacaExecutor
from execution.position_monitor import PositionMonitor


class AutonomousRunner:
    """
    Autonomous orchestrator that executes scheduled cycles across a watchlist:
    1. Position Monitoring & Auto-Exit (Take Profit / Stop Loss).
    2. Capacity & Buying Power validation.
    3. Pipeline execution for candidate watchlist symbols.
    """

    def __init__(
        self,
        watchlist: Optional[List[str]] = None,
        max_open_positions: int = 5,
        scan_interval_seconds: int = 60,
        dry_run: bool = True,
        fetcher: Optional[MarketDataFetcher] = None,
        detector: Optional[RegimeDetector] = None,
        agent: Optional[StrategyAgent] = None,
        gate: Optional[RiskGate] = None,
        executor: Optional[AlpacaExecutor] = None,
        monitor: Optional[PositionMonitor] = None,
    ):
        self.watchlist = watchlist or ["SPY", "AAPL", "NVDA", "QQQ", "MSFT"]
        self.max_open_positions = max_open_positions
        self.scan_interval_seconds = scan_interval_seconds
        self.dry_run = dry_run

        # Initialize modular pipeline components
        self.fetcher = fetcher or MarketDataFetcher()
        self.detector = detector or RegimeDetector()
        self.agent = agent or StrategyAgent()
        self.gate = gate or RiskGate(max_position_size_pct=0.05)
        self.executor = executor or AlpacaExecutor()
        self.monitor = monitor or PositionMonitor()

    def run_iteration(
        self,
        account_override: Optional[Any] = None,
        positions_override: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute one complete autonomous trading cycle.
        """
        cycle_start = datetime.utcnow()
        print(f"\n================================================================================")
        print(f"[{cycle_start.strftime('%Y-%m-%d %H:%M:%S UTC')}] STARTING AUTONOMOUS CYCLE")
        print(f"Watchlist: {self.watchlist} | Max Positions: {self.max_open_positions} | Dry Run: {self.dry_run}")
        print(f"================================================================================")

        # ----------------------------------------------------------------------
        # PHASE 1: Scan & Manage Existing Open Positions (Exit Engine)
        # ----------------------------------------------------------------------
        print("\n[Phase 1] Position Monitor & Exit Engine...")
        exit_results = self.monitor.process_exits(
            positions_override=positions_override,
            dry_run=self.dry_run,
        )

        liquidated_symbols = [
            r["symbol"] for r in exit_results if r.get("action") in ("TAKE_PROFIT", "STOP_LOSS", "TIME_EXIT")
        ]
        active_held_symbols = [
            r["symbol"] for r in exit_results if r.get("action") == "HOLD"
        ]

        print(f"         Evaluated {len(exit_results)} positions:")
        print(f"         - Liquidated / Exited ({len(liquidated_symbols)}): {liquidated_symbols}")
        print(f"         - Actively Held ({len(active_held_symbols)}): {active_held_symbols}")

        # ----------------------------------------------------------------------
        # PHASE 2: Portfolio Capacity & Buying Power Sizing
        # ----------------------------------------------------------------------
        print("\n[Phase 2] Checking Portfolio Slots & Capital Capacity...")
        current_open_count = len(active_held_symbols)
        available_slots = max(0, self.max_open_positions - current_open_count)
        print(f"         Current Open Positions: {current_open_count}/{self.max_open_positions}")
        print(f"         Available Position Slots: {available_slots}")

        # ----------------------------------------------------------------------
        # PHASE 3: Watchlist Scan & Candidate Order Generation
        # ----------------------------------------------------------------------
        print("\n[Phase 3] Scanning Watchlist Candidates...")
        orders_submitted = []
        rejected_proposals = []
        skipped_symbols = []

        for symbol in self.watchlist:
            clean_symbol = symbol.strip().upper()

            # Check if symbol is already in active positions
            if clean_symbol in active_held_symbols:
                print(f"         [-] {clean_symbol}: Skipped (already active position).")
                skipped_symbols.append({"symbol": clean_symbol, "reason": "already_active_position"})
                continue

            # Check if slots are available
            if available_slots <= 0:
                print(f"         [-] {clean_symbol}: Skipped (portfolio capacity reached).")
                skipped_symbols.append({"symbol": clean_symbol, "reason": "portfolio_capacity_full"})
                continue

            print(f"\n         [>] Processing Symbol: {clean_symbol}")
            try:
                # Step 1: Market Data
                bars_df = self.fetcher.get_daily_bars(clean_symbol, days=60)
                
                # Step 2: Regime Analysis
                analysis = self.detector.analyze(clean_symbol, bars_df)
                print(f"             Regime: {analysis.detected_regime.value} (Conf: {analysis.confidence:.2f}, RSI: {analysis.rsi_14:.1f})")

                # Step 3: AI Strategy Formulation
                intent = self.agent.generate_trade_intent(analysis.summary_dict)
                print(f"             Proposed: {intent.strategy_name} ({intent.instrument_type.value}) - Qty: {intent.quantity}")

                # Step 4: Risk Gate Validation
                risk_res = self.gate.evaluate(intent, account_override=account_override)
                if not risk_res.is_approved:
                    print(f"             [X] Risk Gate REJECTED: {risk_res.rejection_reasons}")
                    rejected_proposals.append({
                        "symbol": clean_symbol,
                        "strategy": intent.strategy_name,
                        "reasons": risk_res.rejection_reasons,
                    })
                    continue

                print(f"             [V] Risk Gate APPROVED: Proposed Cost=${risk_res.proposed_cost_usd:,.2f} <= Max=${risk_res.max_allowed_allocation_usd:,.2f}")

                # Step 5: Execution Engine
                exec_receipt = self.executor.execute_intent(intent, dry_run=self.dry_run)
                print(f"             Order Status: {exec_receipt.get('status')} (Order ID: {exec_receipt.get('order_id')})")
                orders_submitted.append({
                    "symbol": clean_symbol,
                    "strategy": intent.strategy_name,
                    "instrument_type": intent.instrument_type.value,
                    "execution": exec_receipt,
                })
                available_slots -= 1

            except Exception as e:
                print(f"             [!] Error processing {clean_symbol}: {e}")
                rejected_proposals.append({"symbol": clean_symbol, "error": str(e)})

        cycle_end = datetime.utcnow()
        duration_sec = (cycle_end - cycle_start).total_seconds()

        cycle_summary = {
            "timestamp": cycle_end.isoformat(),
            "duration_seconds": round(duration_sec, 2),
            "watchlist_scanned": self.watchlist,
            "positions_evaluated": len(exit_results),
            "liquidations_executed": liquidated_symbols,
            "actively_held_positions": active_held_symbols,
            "new_orders_submitted": orders_submitted,
            "rejected_or_failed": rejected_proposals,
            "skipped_candidates": skipped_symbols,
            "available_slots_remaining": available_slots,
        }

        print(f"\n================================================================================")
        print(f"CYCLE COMPLETED in {duration_sec:.2f}s | Orders Placed: {len(orders_submitted)} | Liquidations: {len(liquidated_symbols)}")
        print(f"================================================================================")

        return cycle_summary

    def run_loop(self, max_iterations: Optional[int] = None):
        """
        Continuous daemon scheduler loop with configurable scan interval.
        """
        iteration = 0
        print(f"Autonomous Trading Runner Loop Started. Interval = {self.scan_interval_seconds}s")
        try:
            while True:
                iteration += 1
                print(f"\n--- Iteration #{iteration} ---")
                self.run_iteration()

                if max_iterations and iteration >= max_iterations:
                    print(f"Reached max iterations ({max_iterations}). Terminating loop.")
                    break

                time.sleep(self.scan_interval_seconds)
        except KeyboardInterrupt:
            print("\nAutonomous Trading Runner gracefully stopped by user.")
