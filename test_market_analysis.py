import json
from data.market_fetcher import MarketDataFetcher
from analysis.regime_detector import RegimeDetector
from schemas.trade_intent import MarketRegime


def run_market_analysis_tests():
    print("==================================================")
    print("1. Testing MarketDataFetcher (Live / Offline Data)")
    print("==================================================")

    fetcher = MarketDataFetcher()
    detector = RegimeDetector()

    # Test Fetcher with SPY
    print("Fetching 60 daily bars for SPY...")
    spy_bars = fetcher.get_daily_bars("SPY", days=60)
    print(f" [PASS] Fetched {len(spy_bars)} bars for SPY.")
    print(f"        Columns: {list(spy_bars.columns)}")
    print(f"        Latest Close: ${spy_bars['close'].iloc[-1]:.2f} on {spy_bars['timestamp'].iloc[-1]}")

    print("\n==================================================")
    print("2. Testing Technical Indicators & Regime Detection")
    print("==================================================")

    # Analyze SPY
    spy_analysis = detector.analyze("SPY", spy_bars)
    print(f"\nSPY Regime Detection Result:")
    print(f" - Detected Regime: {spy_analysis.detected_regime.value}")
    print(f" - Confidence: {spy_analysis.confidence:.2f}")
    print(f" - Last Close: ${spy_analysis.last_close:.2f}")
    print(f" - RSI (14): {spy_analysis.rsi_14:.2f}")
    print(f" - SMA (20): ${spy_analysis.sma_20:.2f} | SMA (50): ${spy_analysis.sma_50:.2f}")
    print(f" - ATR (14): ${spy_analysis.atr_14:.2f}")
    print(f" - Realized Volatility: {spy_analysis.realized_volatility:.2f}%")

    assert isinstance(spy_analysis.detected_regime, MarketRegime)
    assert 0.0 <= spy_analysis.confidence <= 1.0
    print("\n [PASS] SPY Regime Analysis returned a valid MarketRegime instance.")

    print("\nSummary Dict for AI Prompt Injection:")
    print(json.dumps(spy_analysis.summary_dict, indent=2))

    print("\n==================================================")
    print("3. Testing Multiple Synthetic Market Regimes")
    print("==================================================")

    # Scenario A: Strong Bullish Trend
    bullish_bars = fetcher.generate_mock_bars("AAPL", days=60, start_price=200.0, trend="bullish", volatility=0.008)
    res_bullish = detector.analyze("AAPL", bullish_bars)
    print(f"- Scenario A (Bullish Trend): Regime={res_bullish.detected_regime.value}, RSI={res_bullish.rsi_14:.1f}")
    assert res_bullish.detected_regime in (MarketRegime.BULLISH_TRENDING, MarketRegime.LOW_VOLATILITY)

    # Scenario B: Strong Bearish Trend
    bearish_bars = fetcher.generate_mock_bars("TSLA", days=60, start_price=250.0, trend="bearish", volatility=0.012)
    res_bearish = detector.analyze("TSLA", bearish_bars)
    print(f"- Scenario B (Bearish Trend): Regime={res_bearish.detected_regime.value}, RSI={res_bearish.rsi_14:.1f}")
    assert res_bearish.detected_regime in (MarketRegime.BEARISH_TRENDING, MarketRegime.HIGH_VOLATILITY)

    # Scenario C: High Volatility Shock
    volatile_bars = fetcher.generate_mock_bars("NVDA", days=60, start_price=120.0, trend="sideways", volatility=0.035)
    res_volatile = detector.analyze("NVDA", volatile_bars)
    print(f"- Scenario C (High Volatility): Regime={res_volatile.detected_regime.value}, Vol={res_volatile.realized_volatility:.1f}%")
    assert res_volatile.detected_regime == MarketRegime.HIGH_VOLATILITY

    print("\n==================================================")
    print("ALL MARKET ANALYSIS & REGIME DETECTOR TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    run_market_analysis_tests()
