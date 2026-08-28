import json
import os
import re
from datetime import date, timedelta
from typing import Any, Dict, Optional
from dotenv import load_dotenv

from schemas.trade_intent import (
    InstrumentType,
    MarketRegime,
    OptionAction,
    OptionLeg,
    OptionType,
    OrderSide,
    TradeIntent,
)


STRATEGY_SYSTEM_PROMPT = """
You are an Elite Quantitative Trading & Options Strategist AI.
Your role is to formulate high-probability, risk-defined trade proposals based on technical market metrics.

Input: Technical Summary JSON containing symbol, regime, price, RSI, SMA 20/50, ATR, Realized Volatility.
Output: MUST be a strict, single JSON object adhering exactly to the TradeIntent schema below.

### Output JSON Schema Specification:
{
  "symbol": string,
  "market_regime": "BULLISH_TRENDING" | "BEARISH_TRENDING" | "SIDEWAYS_CONSOLIDATION" | "HIGH_VOLATILITY" | "LOW_VOLATILITY",
  "instrument_type": "EQUITY" | "OPTION",
  "strategy_name": string,
  "action": "BUY" | "SELL",
  "quantity": integer,
  "estimated_entry_price": float,
  "target_price": float,
  "stop_loss": float,
  "options_legs": [
    {
      "strike_price": float,
      "expiration_date": "YYYY-MM-DD",
      "option_type": "CALL" | "PUT",
      "action": "BUY_TO_OPEN" | "SELL_TO_OPEN",
      "quantity": integer
    }
  ],
  "reasoning": string,
  "confidence_score": float between 0.0 and 1.0
}

### Non-Negotiable Guardrails & Rules:
1. LLM NEVER executes trades. LLM ONLY outputs structured TradeIntent JSON.
2. Market Regime Strategy Guide:
   - BULLISH_TRENDING: Bull Call Spread (BUY call @ lower strike, SELL call @ higher strike) or Long Equity.
   - BEARISH_TRENDING: Bear Put Spread (BUY put @ higher strike, SELL put @ lower strike) or Long Put.
   - HIGH_VOLATILITY: Defined-Risk Spreads (Iron Condor or Credit Spread). NAKED short options are 100% PROHIBITED.
   - SIDEWAYS_CONSOLIDATION / LOW_VOLATILITY: Range-bound defined-risk spreads or Low Delta Bullish/Neutral Spreads.
3. Defined-Risk Options Rule: Every SELL_TO_OPEN leg MUST have a corresponding protective BUY_TO_OPEN leg.
4. Stop Loss:
   - For BUY order: stop_loss < estimated_entry_price.
   - For SELL order: stop_loss > estimated_entry_price.
5. Realistic Pricing: Expiration dates should be 20 to 45 days in the future.
6. Return ONLY the raw JSON object. Do not include markdown preamble.
"""


class StrategyAgent:
    """
    AI-driven strategy formulation agent.
    Combines LLM intelligence with deterministic fallback to generate valid TradeIntent proposals.
    """

    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        load_dotenv()
        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.base_url = base_url or os.getenv("LLM_BASE_URL")

        self.client = None
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url if self.base_url else None,
                )
            except Exception as e:
                print(f"[StrategyAgent] Failed to initialize OpenAI client: {e}")
                self.client = None

    def generate_trade_intent(self, summary_dict: Dict[str, Any]) -> TradeIntent:
        """
        Formulate a TradeIntent proposal based on technical indicators and market regime.
        """
        prompt_input = json.dumps(summary_dict, indent=2)

        # 1. Try LLM Generation if client available
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": STRATEGY_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Generate a trade proposal for the following market metrics:\n{prompt_input}"},
                    ],
                    temperature=0.2,
                    response_format={"type": "json_object"},
                )
                raw_content = response.choices[0].message.content
                return self._parse_and_validate_json(raw_content)
            except Exception as e:
                print(f"[StrategyAgent] LLM API call error ({e}). Engaging deterministic fallback generator...")

        # 2. Resilient Deterministic Strategy Generator (Guaranteed valid TradeIntent)
        return self._generate_deterministic_proposal(summary_dict)

    def _parse_and_validate_json(self, raw_json_str: str) -> TradeIntent:
        """Clean markdown wrapping and validate into Pydantic TradeIntent model."""
        cleaned = re.sub(r"^```json\s*", "", raw_json_str.strip())
        cleaned = re.sub(r"^```\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return TradeIntent.model_validate_json(cleaned)

    def _generate_deterministic_proposal(self, summary_dict: Dict[str, Any]) -> TradeIntent:
        """
        Rule-based deterministic strategy synthesizer adhering strictly to PROJECT_RULES.md.
        Used as resilient fallback or offline execution.
        """
        symbol = summary_dict.get("symbol", "SPY").upper()
        regime_str = summary_dict.get("detected_regime", MarketRegime.BULLISH_TRENDING.value)
        regime = MarketRegime(regime_str)
        last_price = float(summary_dict.get("last_price", 580.0))
        atr = float(summary_dict.get("atr_14", 5.0))
        confidence = float(summary_dict.get("confidence_score", 0.80))
        rationale = summary_dict.get("rationale", "Deterministic regime-aligned quantitative proposal.")

        exp_date = (date.today() + timedelta(days=30)).isoformat()

        if regime == MarketRegime.BULLISH_TRENDING:
            # Bull Call Spread (Defined Risk)
            lower_strike = round(last_price, 0)
            upper_strike = round(last_price + max(5.0, atr * 1.5), 0)
            estimated_premium = round(max(2.0, atr * 0.6), 2)
            target = round(estimated_premium * 2.2, 2)
            stop = round(estimated_premium * 0.45, 2)

            return TradeIntent(
                symbol=symbol,
                market_regime=regime,
                instrument_type=InstrumentType.OPTION,
                strategy_name="BULL_CALL_SPREAD",
                action=OrderSide.BUY,
                quantity=1,
                estimated_entry_price=estimated_premium,
                target_price=target,
                stop_loss=stop,
                options_legs=[
                    OptionLeg(
                        strike_price=lower_strike,
                        expiration_date=exp_date,
                        option_type=OptionType.CALL,
                        action=OptionAction.BUY_TO_OPEN,
                        quantity=1,
                    ),
                    OptionLeg(
                        strike_price=upper_strike,
                        expiration_date=exp_date,
                        option_type=OptionType.CALL,
                        action=OptionAction.SELL_TO_OPEN,
                        quantity=1,
                    ),
                ],
                reasoning=f"Bullish momentum detected. Strategy: Bull Call Spread ${lower_strike}/${upper_strike} strikes to capture upside with capped risk. {rationale}",
                confidence_score=confidence,
            )

        elif regime == MarketRegime.BEARISH_TRENDING:
            # Bear Put Spread (Defined Risk)
            higher_strike = round(last_price, 0)
            lower_strike = round(last_price - max(5.0, atr * 1.5), 0)
            estimated_premium = round(max(2.0, atr * 0.6), 2)
            target = round(estimated_premium * 2.2, 2)
            stop = round(estimated_premium * 0.45, 2)

            return TradeIntent(
                symbol=symbol,
                market_regime=regime,
                instrument_type=InstrumentType.OPTION,
                strategy_name="BEAR_PUT_SPREAD",
                action=OrderSide.BUY,
                quantity=1,
                estimated_entry_price=estimated_premium,
                target_price=target,
                stop_loss=stop,
                options_legs=[
                    OptionLeg(
                        strike_price=higher_strike,
                        expiration_date=exp_date,
                        option_type=OptionType.PUT,
                        action=OptionAction.BUY_TO_OPEN,
                        quantity=1,
                    ),
                    OptionLeg(
                        strike_price=lower_strike,
                        expiration_date=exp_date,
                        option_type=OptionType.PUT,
                        action=OptionAction.SELL_TO_OPEN,
                        quantity=1,
                    ),
                ],
                reasoning=f"Bearish breakdown detected. Strategy: Bear Put Spread ${higher_strike}/${lower_strike} strikes for defined-risk downside positioning. {rationale}",
                confidence_score=confidence,
            )

        elif regime == MarketRegime.HIGH_VOLATILITY:
            # Iron Condor (Defined Risk)
            put_sell = round(last_price - (atr * 2.0), 0)
            put_buy = round(put_sell - 5.0, 0)
            call_sell = round(last_price + (atr * 2.0), 0)
            call_buy = round(call_sell + 5.0, 0)
            credit_premium = 1.80

            return TradeIntent(
                symbol=symbol,
                market_regime=regime,
                instrument_type=InstrumentType.OPTION,
                strategy_name="IRON_CONDOR",
                action=OrderSide.BUY,
                quantity=1,
                estimated_entry_price=credit_premium,
                target_price=round(credit_premium * 1.8, 2),
                stop_loss=round(credit_premium * 0.5, 2),
                options_legs=[
                    OptionLeg(strike_price=put_buy, expiration_date=exp_date, option_type=OptionType.PUT, action=OptionAction.BUY_TO_OPEN, quantity=1),
                    OptionLeg(strike_price=put_sell, expiration_date=exp_date, option_type=OptionType.PUT, action=OptionAction.SELL_TO_OPEN, quantity=1),
                    OptionLeg(strike_price=call_sell, expiration_date=exp_date, option_type=OptionType.CALL, action=OptionAction.SELL_TO_OPEN, quantity=1),
                    OptionLeg(strike_price=call_buy, expiration_date=exp_date, option_type=OptionType.CALL, action=OptionAction.BUY_TO_OPEN, quantity=1),
                ],
                reasoning=f"High volatility expansion. Strategy: Defined-risk Iron Condor to capture volatility contraction. {rationale}",
                confidence_score=confidence,
            )

        else: # SIDEWAYS_CONSOLIDATION or LOW_VOLATILITY
            # Defined-risk Range Bound Spread or Equity Long with Tight Stop
            entry = last_price
            target = round(entry + (atr * 1.5), 2)
            stop = round(entry - (atr * 0.8), 2)

            return TradeIntent(
                symbol=symbol,
                market_regime=regime,
                instrument_type=InstrumentType.EQUITY,
                strategy_name="EQUITY_RANGE_TRADE",
                action=OrderSide.BUY,
                quantity=5,
                estimated_entry_price=entry,
                target_price=target,
                stop_loss=stop,
                options_legs=[],
                reasoning=f"Range-bound consolidation. Strategy: Moderate equity swing position within support/resistance channel. {rationale}",
                confidence_score=confidence,
            )
