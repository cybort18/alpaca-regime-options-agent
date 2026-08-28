import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.models import Position
except ImportError:
    TradingClient = Any
    Position = Any


@dataclass
class PositionExitSignal:
    """Represents an exit decision signal evaluated for an open position."""
    symbol: str
    action: str  # "HOLD", "TAKE_PROFIT", "STOP_LOSS", "TIME_EXIT"
    unrealized_pl: float
    unrealized_plpc: float
    current_price: float
    avg_entry_price: float
    qty: float
    reason: str


class PositionMonitor:
    """
    Monitors all open Alpaca positions (equities and options).
    Evaluates unrealized P&L and triggers profit-taking or hard stop-loss liquidations.
    """

    def __init__(
        self,
        trading_client: Optional[TradingClient] = None,
        profit_target_pct: float = 0.50,  # e.g., +50% profit target
        stop_loss_pct: float = 0.40,       # e.g., -40% hard stop loss
    ):
        load_dotenv()
        self.profit_target_pct = profit_target_pct
        self.stop_loss_pct = stop_loss_pct

        if trading_client:
            self.client = trading_client
        else:
            api_key = os.getenv("ALPACA_API_KEY")
            secret_key = os.getenv("ALPACA_SECRET_KEY")
            paper = os.getenv("ALPACA_PAPER", "True").lower() in ("true", "1", "yes")

            if api_key and secret_key:
                try:
                    self.client = TradingClient(api_key=api_key, secret_key=secret_key, paper=paper)
                except Exception as e:
                    print(f"[PositionMonitor] Client init warning: {e}")
                    self.client = None
            else:
                self.client = None

    def get_open_positions(self) -> List[Any]:
        """Fetch all currently open positions from Alpaca."""
        if not self.client:
            return []
        try:
            return self.client.get_all_positions()
        except Exception as e:
            print(f"[PositionMonitor] Error fetching positions: {e}")
            return []

    def evaluate_position(self, pos: Any) -> PositionExitSignal:
        """
        Evaluate a single position against defined exit criteria.
        """
        symbol = getattr(pos, "symbol", "UNKNOWN")
        qty = float(getattr(pos, "qty", 0.0))
        entry_price = float(getattr(pos, "avg_entry_price", 0.0))
        current_price = float(getattr(pos, "current_price", 0.0))
        unrealized_pl = float(getattr(pos, "unrealized_pl", 0.0))
        unrealized_plpc = float(getattr(pos, "unrealized_plpc", 0.0))

        # Check Profit Target Exit (e.g. >= +50%)
        if unrealized_plpc >= self.profit_target_pct:
            return PositionExitSignal(
                symbol=symbol,
                action="TAKE_PROFIT",
                unrealized_pl=unrealized_pl,
                unrealized_plpc=unrealized_plpc,
                current_price=current_price,
                avg_entry_price=entry_price,
                qty=qty,
                reason=f"Profit target hit: Unrealized gain +{unrealized_plpc*100:.2f}% >= target threshold (+{self.profit_target_pct*100:.1f}%)"
            )

        # Check Hard Stop-Loss Exit (e.g. <= -40%)
        if unrealized_plpc <= -abs(self.stop_loss_pct):
            return PositionExitSignal(
                symbol=symbol,
                action="STOP_LOSS",
                unrealized_pl=unrealized_pl,
                unrealized_plpc=unrealized_plpc,
                current_price=current_price,
                avg_entry_price=entry_price,
                qty=qty,
                reason=f"Hard stop-loss triggered: Unrealized loss {unrealized_plpc*100:.2f}% <= max loss threshold (-{abs(self.stop_loss_pct)*100:.1f}%)"
            )

        # Default: Hold position
        return PositionExitSignal(
            symbol=symbol,
            action="HOLD",
            unrealized_pl=unrealized_pl,
            unrealized_plpc=unrealized_plpc,
            current_price=current_price,
            avg_entry_price=entry_price,
            qty=qty,
            reason=f"Position healthy: PnL {unrealized_plpc*100:+.2f}% within risk boundaries."
        )

    def close_position(
        self,
        symbol: str,
        qty: Optional[float] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Close/liquidate an open position.
        """
        if dry_run or not self.client:
            return {
                "success": True,
                "is_dry_run": True,
                "symbol": symbol,
                "status": "simulated_closed",
                "closed_at": datetime.utcnow().isoformat(),
                "qty": qty,
                "message": f"Simulated liquidation of {symbol} executed successfully."
            }

        try:
            res = self.client.close_position(symbol_or_asset_id=symbol)
            return {
                "success": True,
                "is_dry_run": False,
                "symbol": symbol,
                "order_id": str(getattr(res, "id", "")),
                "status": str(getattr(res, "status", "pending_close")),
                "closed_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            return {
                "success": False,
                "symbol": symbol,
                "error": str(e),
            }

    def process_exits(
        self,
        positions_override: Optional[List[Any]] = None,
        dry_run: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Scan all open positions, evaluate exit signals, and execute liquidations when triggered.
        """
        positions = positions_override if positions_override is not None else self.get_open_positions()
        results = []

        for pos in positions:
            signal = self.evaluate_position(pos)
            if signal.action in ("TAKE_PROFIT", "STOP_LOSS", "TIME_EXIT"):
                close_res = self.close_position(symbol=signal.symbol, qty=signal.qty, dry_run=dry_run)
                results.append({
                    "symbol": signal.symbol,
                    "action": signal.action,
                    "reason": signal.reason,
                    "unrealized_pl": signal.unrealized_pl,
                    "unrealized_plpc": signal.unrealized_plpc,
                    "liquidation_result": close_res,
                })
            else:
                results.append({
                    "symbol": signal.symbol,
                    "action": "HOLD",
                    "reason": signal.reason,
                    "unrealized_pl": signal.unrealized_pl,
                    "unrealized_plpc": signal.unrealized_plpc,
                })

        return results
