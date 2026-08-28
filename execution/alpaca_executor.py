import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

from schemas.trade_intent import (
    InstrumentType,
    OptionAction,
    OptionLeg,
    OptionType,
    OrderSide,
    TradeIntent,
)

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import OrderSide as AlpacaOrderSide
    from alpaca.trading.enums import TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
except ImportError:
    TradingClient = Any
    MarketOrderRequest = Any
    LimitOrderRequest = Any
    AlpacaOrderSide = Any
    TimeInForce = Any


class AlpacaExecutor:
    """
    Executes validated and risk-cleared TradeIntent objects via Alpaca Trading API.
    Supports both Equity and Options strategies, with dry-run capabilities.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        paper: bool = True,
        trading_client: Optional[TradingClient] = None,
    ):
        load_dotenv()
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")
        self.paper = paper

        if trading_client:
            self.client = trading_client
        elif self.api_key and self.secret_key:
            try:
                self.client = TradingClient(
                    api_key=self.api_key,
                    secret_key=self.secret_key,
                    paper=self.paper,
                )
            except Exception as e:
                print(f"[AlpacaExecutor] TradingClient initialization warning: {e}")
                self.client = None
        else:
            self.client = None

    @staticmethod
    def format_occ_option_symbol(
        underlying: str,
        expiration_date_str: str,
        option_type: OptionType,
        strike_price: float,
    ) -> str:
        """
        Converts option parameters to standard OCC Option Symbol.
        Format: TICKER + YYMMDD + (C/P) + 8-digit price (price * 1000)
        Example: AAPL, 2026-09-18, CALL, 220.0 -> AAPL260918C00220000
        """
        clean_symbol = underlying.strip().upper()
        # Parse expiration date YYYY-MM-DD
        dt = datetime.strptime(expiration_date_str, "%Y-%m-%d")
        yymmdd = dt.strftime("%y%m%d")
        opt_char = "C" if option_type == OptionType.CALL else "P"
        # Strike price formatted with 3 decimal places in 8 characters
        strike_int = int(round(strike_price * 1000))
        strike_str = f"{strike_int:08d}"
        
        return f"{clean_symbol}{yymmdd}{opt_char}{strike_str}"

    def execute_intent(
        self,
        intent: TradeIntent,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a validated TradeIntent proposal.
        """
        if dry_run or not self.client:
            return self._execute_dry_run(intent)

        try:
            if intent.instrument_type == InstrumentType.EQUITY:
                return self._execute_equity_order(intent)
            elif intent.instrument_type == InstrumentType.OPTION:
                return self._execute_option_order(intent)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported instrument_type: {intent.instrument_type}",
                }
        except Exception as e:
            # Fallback to dry-run reporting if network fails
            print(f"[AlpacaExecutor] Live execution exception ({e}). Returning dry-run simulated execution receipt.")
            res = self._execute_dry_run(intent)
            res["live_error"] = str(e)
            return res

    def _execute_equity_order(self, intent: TradeIntent) -> Dict[str, Any]:
        """Submit equity market or limit order to Alpaca."""
        side = AlpacaOrderSide.BUY if intent.action == OrderSide.BUY else AlpacaOrderSide.SELL
        
        if intent.estimated_entry_price:
            order_req = LimitOrderRequest(
                symbol=intent.symbol,
                qty=intent.quantity,
                side=side,
                time_in_force=TimeInForce.DAY,
                limit_price=round(intent.estimated_entry_price, 2),
            )
        else:
            order_req = MarketOrderRequest(
                symbol=intent.symbol,
                qty=intent.quantity,
                side=side,
                time_in_force=TimeInForce.DAY,
            )

        order = self.client.submit_order(order_req)
        return {
            "success": True,
            "order_id": str(order.id),
            "client_order_id": str(order.client_order_id),
            "symbol": intent.symbol,
            "instrument_type": intent.instrument_type.value,
            "strategy": intent.strategy_name or "EQUITY",
            "quantity": intent.quantity,
            "status": str(order.status),
            "submitted_at": datetime.utcnow().isoformat(),
            "target_price": intent.target_price,
            "stop_loss": intent.stop_loss,
        }

    def _execute_option_order(self, intent: TradeIntent) -> Dict[str, Any]:
        """Submit options order legs to Alpaca."""
        submitted_legs = []
        for leg in intent.options_legs:
            occ_symbol = self.format_occ_option_symbol(
                underlying=intent.symbol,
                expiration_date_str=leg.expiration_date,
                option_type=leg.option_type,
                strike_price=leg.strike_price,
            )
            side = AlpacaOrderSide.BUY if "BUY" in leg.action.value else AlpacaOrderSide.SELL
            
            order_req = MarketOrderRequest(
                symbol=occ_symbol,
                qty=leg.quantity * intent.quantity,
                side=side,
                time_in_force=TimeInForce.DAY,
            )
            order = self.client.submit_order(order_req)
            submitted_legs.append({
                "occ_symbol": occ_symbol,
                "order_id": str(order.id),
                "side": leg.action.value,
                "quantity": leg.quantity * intent.quantity,
                "status": str(order.status),
            })

        return {
            "success": True,
            "symbol": intent.symbol,
            "instrument_type": intent.instrument_type.value,
            "strategy": intent.strategy_name or "OPTION_SPREAD",
            "legs": submitted_legs,
            "submitted_at": datetime.utcnow().isoformat(),
            "target_price": intent.target_price,
            "stop_loss": intent.stop_loss,
        }

    def _execute_dry_run(self, intent: TradeIntent) -> Dict[str, Any]:
        """Simulate execution for offline validation and paper dry-run."""
        simulated_order_id = str(uuid.uuid4())
        
        if intent.instrument_type == InstrumentType.OPTION:
            formatted_legs = []
            for leg in intent.options_legs:
                occ_sym = self.format_occ_option_symbol(
                    underlying=intent.symbol,
                    expiration_date_str=leg.expiration_date,
                    option_type=leg.option_type,
                    strike_price=leg.strike_price,
                )
                formatted_legs.append({
                    "occ_symbol": occ_sym,
                    "action": leg.action.value,
                    "strike": leg.strike_price,
                    "expiration": leg.expiration_date,
                    "quantity": leg.quantity * intent.quantity,
                    "status": "simulated_filled",
                })

            return {
                "success": True,
                "is_dry_run": True,
                "order_id": simulated_order_id,
                "symbol": intent.symbol,
                "instrument_type": intent.instrument_type.value,
                "strategy": intent.strategy_name,
                "quantity": intent.quantity,
                "estimated_entry_price": intent.estimated_entry_price,
                "legs": formatted_legs,
                "status": "simulated_accepted",
                "submitted_at": datetime.utcnow().isoformat(),
                "target_price": intent.target_price,
                "stop_loss": intent.stop_loss,
                "reasoning": intent.reasoning,
            }
        else:
            return {
                "success": True,
                "is_dry_run": True,
                "order_id": simulated_order_id,
                "symbol": intent.symbol,
                "instrument_type": intent.instrument_type.value,
                "strategy": intent.strategy_name,
                "action": intent.action.value,
                "quantity": intent.quantity,
                "estimated_entry_price": intent.estimated_entry_price,
                "status": "simulated_accepted",
                "submitted_at": datetime.utcnow().isoformat(),
                "target_price": intent.target_price,
                "stop_loss": intent.stop_loss,
                "reasoning": intent.reasoning,
            }
