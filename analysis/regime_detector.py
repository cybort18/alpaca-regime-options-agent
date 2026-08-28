from dataclasses import dataclass
from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

from schemas.trade_intent import MarketRegime


@dataclass
class RegimeAnalysisResult:
    """Structured output containing regime classification, confidence, and metrics."""
    symbol: str
    detected_regime: MarketRegime
    confidence: float
    summary_dict: Dict[str, Any]
    last_close: float
    rsi_14: float
    sma_20: float
    sma_50: float
    atr_14: float
    realized_volatility: float


class RegimeDetector:
    """
    Lightweight, deterministic technical regime classifier using pure pandas/numpy.
    Analyzes trend direction, momentum (RSI), and volatility (ATR & Realized Vol).
    """

    def __init__(
        self,
        sma_fast_window: int = 20,
        sma_slow_window: int = 50,
        rsi_window: int = 14,
        atr_window: int = 14,
        volatility_window: int = 20,
    ):
        self.fast_window = sma_fast_window
        self.slow_window = sma_slow_window
        self.rsi_window = rsi_window
        self.atr_window = atr_window
        self.vol_window = volatility_window

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute SMA 20/50, RSI 14, ATR 14, and Realized Volatility.
        """
        data = df.copy()
        if "close" not in data.columns:
            raise ValueError("Input DataFrame must contain 'close' column.")

        # 1. Moving Averages
        data["sma_fast"] = data["close"].rolling(window=self.fast_window).mean()
        data["sma_slow"] = data["close"].rolling(window=self.slow_window).mean()

        # 2. RSI (Relative Strength Index)
        delta = data["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        
        # Exponential or simple smoothed averages for RSI
        avg_gain = gain.rolling(window=self.rsi_window, min_periods=self.rsi_window).mean()
        avg_loss = loss.rolling(window=self.rsi_window, min_periods=self.rsi_window).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        data["rsi"] = 100.0 - (100.0 / (1.0 + rs))

        # 3. ATR (Average True Range)
        if "high" in data.columns and "low" in data.columns:
            prev_close = data["close"].shift(1)
            tr1 = data["high"] - data["low"]
            tr2 = (data["high"] - prev_close).abs()
            tr3 = (data["low"] - prev_close).abs()
            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            data["atr"] = true_range.rolling(window=self.atr_window).mean()
            data["atr_pct"] = (data["atr"] / data["close"]) * 100.0
        else:
            data["atr"] = 0.0
            data["atr_pct"] = 0.0

        # 4. Realized Volatility (Annualized Percentage)
        returns = data["close"].pct_change()
        data["realized_vol"] = returns.rolling(window=self.vol_window).std() * np.sqrt(252) * 100.0

        # 5. Bollinger Bands & Bandwidth
        rolling_std = data["close"].rolling(window=self.fast_window).std()
        data["bb_upper"] = data["sma_fast"] + (2.0 * rolling_std)
        data["bb_lower"] = data["sma_fast"] - (2.0 * rolling_std)
        data["bb_bandwidth"] = (data["bb_upper"] - data["bb_lower"]) / (data["sma_fast"] + 1e-9) * 100.0

        return data

    def analyze(self, symbol: str, df: pd.DataFrame) -> RegimeAnalysisResult:
        """
        Classifies the market regime for the given symbol's price series.
        """
        data = self.compute_indicators(df)
        last_row = data.iloc[-1]

        close = float(last_row["close"])
        sma_20 = float(last_row["sma_fast"]) if pd.notnull(last_row["sma_fast"]) else close
        sma_50 = float(last_row["sma_slow"]) if pd.notnull(last_row["sma_slow"]) else sma_20
        rsi = float(last_row["rsi"]) if pd.notnull(last_row["rsi"]) else 50.0
        atr = float(last_row["atr"]) if pd.notnull(last_row["atr"]) else 0.0
        atr_pct = float(last_row["atr_pct"]) if pd.notnull(last_row["atr_pct"]) else 0.0
        vol = float(last_row["realized_vol"]) if pd.notnull(last_row["realized_vol"]) else 15.0
        bandwidth = float(last_row["bb_bandwidth"]) if pd.notnull(last_row["bb_bandwidth"]) else 4.0

        # Slope of SMA 20 (over past 5 bars)
        if len(data) >= 5 and pd.notnull(data["sma_fast"].iloc[-5]):
            sma_20_slope = (sma_20 - data["sma_fast"].iloc[-5]) / data["sma_fast"].iloc[-5] * 100.0
        else:
            sma_20_slope = 0.0

        price_vs_sma20 = ((close - sma_20) / sma_20) * 100.0
        price_vs_sma50 = ((close - sma_50) / sma_50) * 100.0

        # --- Regime Classification Logic ---
        confidence = 0.75
        rationale = []

        # 1. High Volatility Check
        if vol >= 28.0 or atr_pct >= 2.3 or bandwidth >= 10.0:
            regime = MarketRegime.HIGH_VOLATILITY
            confidence = min(0.95, 0.70 + (vol / 100.0))
            rationale.append(f"Realized Volatility is elevated at {vol:.1f}% (ATR: {atr_pct:.2f}%).")

        # 2. Bullish Trending Check
        elif close >= sma_20 and sma_20 >= sma_50 and rsi >= 50.0 and sma_20_slope > 0:
            regime = MarketRegime.BULLISH_TRENDING
            confidence = 0.85 if (rsi >= 55.0 and price_vs_sma20 > 0.5) else 0.75
            rationale.append(f"Price (${close:.2f}) > SMA20 (${sma_20:.2f}) > SMA50 (${sma_50:.2f}) with RSI={rsi:.1f}.")

        # 3. Bearish Trending Check
        elif close <= sma_20 and sma_20 <= sma_50 and rsi <= 50.0 and sma_20_slope < 0:
            regime = MarketRegime.BEARISH_TRENDING
            confidence = 0.85 if (rsi <= 45.0 and price_vs_sma20 < -0.5) else 0.75
            rationale.append(f"Price (${close:.2f}) < SMA20 (${sma_20:.2f}) < SMA50 (${sma_50:.2f}) with RSI={rsi:.1f}.")

        # 4. Low Volatility / Squeeze Check
        elif vol <= 12.0 and atr_pct <= 0.95 and bandwidth <= 3.5:
            regime = MarketRegime.LOW_VOLATILITY
            confidence = 0.82
            rationale.append(f"Volatility compressed: Vol={vol:.1f}%, ATR={atr_pct:.2f}%, Bandwidth={bandwidth:.2f}%.")

        # 5. Sideways Consolidation (Default / Oscillating)
        else:
            regime = MarketRegime.SIDEWAYS_CONSOLIDATION
            confidence = 0.70
            rationale.append(f"Range-bound consolidation around SMA20 (${sma_20:.2f}) with RSI={rsi:.1f}.")

        summary_dict = {
            "symbol": symbol.upper(),
            "detected_regime": regime.value,
            "confidence_score": round(confidence, 2),
            "last_price": round(close, 2),
            "sma_20": round(sma_20, 2),
            "sma_50": round(sma_50, 2),
            "price_vs_sma20_pct": round(price_vs_sma20, 2),
            "price_vs_sma50_pct": round(price_vs_sma50, 2),
            "rsi_14": round(rsi, 2),
            "atr_14": round(atr, 2),
            "atr_pct": round(atr_pct, 2),
            "realized_volatility_pct": round(vol, 2),
            "bb_bandwidth_pct": round(bandwidth, 2),
            "sma_20_slope_pct": round(sma_20_slope, 2),
            "rationale": " ".join(rationale),
        }

        return RegimeAnalysisResult(
            symbol=symbol.upper(),
            detected_regime=regime,
            confidence=confidence,
            summary_dict=summary_dict,
            last_close=close,
            rsi_14=rsi,
            sma_20=sma_20,
            sma_50=sma_50,
            atr_14=atr,
            realized_volatility=vol,
        )
