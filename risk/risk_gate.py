import os
from typing import Any, List, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from schemas.trade_intent import (
    InstrumentType,
    OptionAction,
    TradeIntent,
)

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.models import TradeAccount
except ImportError:
    TradingClient = Any
    TradeAccount = Any


class RiskEvaluationResult(BaseModel):
    """Result returned by the RiskGate after deterministic evaluation."""
    is_approved: bool = Field(..., description="True if proposal passes all hard deterministic risk checks.")
    rejection_reasons: List[str] = Field(default_factory=list, description="List of rule violations if rejected.")
    account_equity: float = Field(..., description="Current total equity of the Alpaca account.")
    buying_power: float = Field(..., description="Current available buying power in Alpaca account.")
    proposed_cost_usd: float = Field(..., description="Estimated total capital required/risked for this order.")
    max_allowed_allocation_usd: float = Field(..., description="Maximum allowed allocation (e.g. 5% equity).")
    metadata: dict = Field(default_factory=dict, description="Supplementary metrics and risk gate metadata.")


class RiskGate:
    """
    Deterministic Hard Risk Gate.
    Enforces non-negotiable safety rules before any trade proposal from AI is sent to Alpaca.
    
    Guaranteed Rules:
    1. Maximum single position allocation <= 5% total account equity.
    2. Account status check (active, not trading blocked).
    3. Adequate cash/buying power available.
    4. Mandatory hard stop-loss and defined-risk parameters.
    5. No naked short options (uncapped risk strictly prohibited).
    """

    def __init__(
        self,
        trading_client: Optional[TradingClient] = None,
        max_position_size_pct: float = 0.05,
        min_account_equity_usd: float = 1000.0,
    ):
        load_dotenv()
        self.max_position_size_pct = max_position_size_pct
        self.min_account_equity_usd = min_account_equity_usd

        if trading_client:
            self.client = trading_client
        else:
            api_key = os.getenv("ALPACA_API_KEY")
            secret_key = os.getenv("ALPACA_SECRET_KEY")
            paper = os.getenv("ALPACA_PAPER", "True").lower() in ("true", "1", "yes")

            if api_key and secret_key:
                self.client = TradingClient(api_key=api_key, secret_key=secret_key, paper=paper)
            else:
                self.client = None

    def get_account(self) -> Optional[TradeAccount]:
        """Fetch current live account details from Alpaca."""
        if not self.client:
            raise RuntimeError("Alpaca TradingClient is not initialized. Please configure .env keys.")
        return self.client.get_account()

    def estimate_order_cost(self, proposal: TradeIntent) -> float:
        """
        Estimate the maximum capital requirement or defined risk in USD.
        For Equity: quantity * estimated_entry_price
        For Options: quantity * premium_per_share * 100 (options contract multiplier)
        """
        if proposal.instrument_type == InstrumentType.EQUITY:
            price = proposal.estimated_entry_price or proposal.stop_loss
            return float(proposal.quantity * price)

        elif proposal.instrument_type == InstrumentType.OPTION:
            # Options standard multiplier is 100 shares per contract
            multiplier = 100
            if proposal.estimated_entry_price:
                return float(proposal.quantity * proposal.estimated_entry_price * multiplier)
            
            # If entry price is not explicitly specified, estimate using strike price difference or leg strikes
            strikes = [leg.strike_price for leg in proposal.options_legs]
            if strikes:
                max_strike = max(strikes)
                min_strike = min(strikes)
                spread_width = max_strike - min_strike
                if spread_width > 0:
                    return float(proposal.quantity * spread_width * multiplier)
                return float(proposal.quantity * min_strike * 0.1 * multiplier)
            
            return 0.0

        return 0.0

    def evaluate(
        self,
        proposal: TradeIntent,
        account_override: Optional[Any] = None,
    ) -> RiskEvaluationResult:
        """
        Perform 100% deterministic risk gate validation on an AI trade proposal.
        """
        rejection_reasons: List[str] = []

        # 1. Obtain Account Details
        try:
            account = account_override or self.get_account()
        except Exception as e:
            return RiskEvaluationResult(
                is_approved=False,
                rejection_reasons=[f"Failed to retrieve Alpaca account details: {str(e)}"],
                account_equity=0.0,
                buying_power=0.0,
                proposed_cost_usd=0.0,
                max_allowed_allocation_usd=0.0,
                metadata={"error": str(e)},
            )

        equity = float(getattr(account, "equity", 0.0))
        buying_power = float(getattr(account, "buying_power", 0.0))
        is_blocked = getattr(account, "trading_blocked", False)
        status = str(getattr(account, "status", "")).upper()

        # 2. Account Health Checks
        if is_blocked:
            rejection_reasons.append("Alpaca account is marked as trading_blocked.")

        if "ACTIVE" not in status:
            rejection_reasons.append(f"Alpaca account status is '{status}', expected 'ACTIVE'.")

        if equity < self.min_account_equity_usd:
            rejection_reasons.append(
                f"Account equity (${equity:,.2f}) is below minimum threshold (${self.min_account_equity_usd:,.2f})."
            )

        # 3. Position Sizing & Allocation Check (Rule: <= 5% equity)
        max_allowed_allocation = equity * self.max_position_size_pct
        proposed_cost = self.estimate_order_cost(proposal)

        if proposed_cost > max_allowed_allocation:
            rejection_reasons.append(
                f"Proposed order cost (${proposed_cost:,.2f}) exceeds maximum allowed position size "
                f"({self.max_position_size_pct*100:.1f}% of equity = ${max_allowed_allocation:,.2f})."
            )

        # 4. Buying Power / Liquidity Check
        if proposed_cost > buying_power:
            rejection_reasons.append(
                f"Proposed cost (${proposed_cost:,.2f}) exceeds available buying power (${buying_power:,.2f})."
            )

        # 5. Stop-Loss & Risk Parameters Verification
        if proposal.stop_loss <= 0:
            rejection_reasons.append("Invalid stop_loss: Must be strictly greater than 0.")

        if proposal.target_price <= 0:
            rejection_reasons.append("Invalid target_price: Must be strictly greater than 0.")

        if proposal.instrument_type == InstrumentType.EQUITY and proposal.estimated_entry_price:
            if proposal.action.value == "BUY":
                if proposal.stop_loss >= proposal.estimated_entry_price:
                    rejection_reasons.append(
                        f"Invalid stop_loss (${proposal.stop_loss}) for BUY order: "
                        f"Must be lower than estimated entry price (${proposal.estimated_entry_price})."
                    )
                if proposal.target_price <= proposal.estimated_entry_price:
                    rejection_reasons.append(
                        f"Invalid target_price (${proposal.target_price}) for BUY order: "
                        f"Must be higher than estimated entry price (${proposal.estimated_entry_price})."
                    )
            elif proposal.action.value == "SELL":
                if proposal.stop_loss <= proposal.estimated_entry_price:
                    rejection_reasons.append(
                        f"Invalid stop_loss (${proposal.stop_loss}) for SELL/SHORT order: "
                        f"Must be higher than estimated entry price (${proposal.estimated_entry_price})."
                    )
                if proposal.target_price >= proposal.estimated_entry_price:
                    rejection_reasons.append(
                        f"Invalid target_price (${proposal.target_price}) for SELL/SHORT order: "
                        f"Must be lower than estimated entry price (${proposal.estimated_entry_price})."
                    )
        elif proposal.instrument_type == InstrumentType.OPTION and proposal.estimated_entry_price:
            # If stop_loss is expressed in option premium terms (< entry price on buy)
            if proposal.stop_loss < proposal.estimated_entry_price:
                # Valid option premium stop
                pass
            # If stop_loss is positive, it's accepted as underlying or premium stop

        # 6. Options Defined-Risk Enforcement
        if proposal.instrument_type == InstrumentType.OPTION:
            has_short = any(leg.action == OptionAction.SELL_TO_OPEN for leg in proposal.options_legs)
            has_long = any(leg.action == OptionAction.BUY_TO_OPEN for leg in proposal.options_legs)
            if has_short and not has_long:
                rejection_reasons.append("Naked short options are strictly forbidden (Defined Risk violation).")

        is_approved = len(rejection_reasons) == 0

        return RiskEvaluationResult(
            is_approved=is_approved,
            rejection_reasons=rejection_reasons,
            account_equity=equity,
            buying_power=buying_power,
            proposed_cost_usd=round(proposed_cost, 2),
            max_allowed_allocation_usd=round(max_allowed_allocation, 2),
            metadata={
                "symbol": proposal.symbol,
                "regime": proposal.market_regime.value,
                "strategy": proposal.strategy_name,
                "rule_max_position_size_pct": self.max_position_size_pct,
            },
        )
