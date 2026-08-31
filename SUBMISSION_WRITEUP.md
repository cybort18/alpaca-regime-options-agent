# Alpaca Regime-Aware AI Options & Equity Trading Agent
**Hackathon Submission Write-up | LabLab.ai Alpaca AI Trading Agents Hackathon**

---

## 1. Executive Summary & Core Objective
The **Alpaca Regime-Aware AI Options & Equity Trading Agent** is an autonomous, quantitative algorithmic trading system engineered for institutional-grade reliability, capital preservation, and multi-regime adaptability. 

Unlike traditional AI trading bots that grant unconstrained direct broker access to large language models (LLMs), our system implements a **strictly isolated, multi-step pipeline**. Google Gemini serves as a quantitative strategy synthesizer that formulates structured trade proposals, while a **100% deterministic mathematical Risk Gate** acts as an impassable barrier before any order can reach the Alpaca Trading API.

---

## 2. Quantitative AI Logic & Dynamic Regime Mapping
The trading engine continuously classifies the market into 5 distinct regimes using pure technical metrics (`SMA 20/50`, `RSI 14`, `ATR 14`, `Realized Volatility`, and `Bollinger Bandwidth`):

1. **BULLISH_TRENDING**: Momentum expansion above ascending SMAs $\rightarrow$ **Bull Call Spreads** (debit spreads capping upside volatility) or **Long Equity**.
2. **BEARISH_TRENDING**: Breakdown below descending SMAs $\rightarrow$ **Bear Put Spreads** (defined-risk downside positioning).
3. **HIGH_VOLATILITY**: Volatility expansion above historical bands $\rightarrow$ **4-Leg Iron Condors** (harvesting elevated implied volatility outside 1.5 ATR wings).
4. **SIDEWAYS_CONSOLIDATION & LOW_VOLATILITY**: Range-bound channel compression $\rightarrow$ **Range Swings** or **Credit Spreads**.

**Smart Friday Options Expiration Picker**: To eliminate unlisted contract rejections, the engine dynamically calculates active US exchange Friday expiration dates (2 to 6 weeks out) and standardized ATM strikes, enforcing that the LLM selects valid, liquid option contracts.

---

## 3. Deterministic Hard Risk Gate (Zero Halucination Policy)
Before any order reaches the Alpaca broker, the proposal must pass four non-negotiable mathematical assertions in pure Python:
- **Max Position Allocation**: Strictly capped at **$\le 5.0\%$ of total account equity** ($5,000 max cost on a $100,000 account).
- **Defined-Risk Enforcement**: Naked short options are **100% prohibited** at both Pydantic schema and RiskGate levels; every short leg must have a protective long leg.
- **Liquidity & Buying Power**: Verified against live real-time account buying power and cash balance.
- **Directional Sanity**: Strict validation of stop-loss and profit targets relative to estimated entry prices.

---

## 4. Alpaca Infrastructure Implementation
- **Alpaca Trading & Market Data API**: Historical daily bars, active options chains, OCC Option Symbol formatting (`TICKER + YYMMDD + C/P + STRIKE`), and live order submission.
- **Model Context Protocol (MCP) Server**: Official FastMCP server exposing 7 quantitative tools (`detect_market_regime`, `get_account_risk_summary`, `evaluate_risk_gate`, `generate_ai_strategy`, `execute_alpaca_order`, `monitor_and_liquidate_positions`, `run_autonomous_pipeline`) for agentic orchestration.
- **Autonomous Daemon & CLI**: Background continuous scheduler (`python cli.py daemon --interval 60`) tracking active positions, executing automated take-profit (+50%) and stop-loss (-40%) liquidations, and scanning watchlists.
- **Explainability Dashboard**: Interactive Streamlit & Plotly interface providing transparent visibility into AI quantitative rationale, active P&L monitors, and mathematical risk compliance.

---

**Repository URL**: `https://github.com/cybort18/alpaca-regime-options-agent.git`
