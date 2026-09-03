# Autonomous Regime-Aware Options & Equity Trading Agent
**Alpaca AI Trading Agents Hackathon Submission Write-up | LabLab.ai**

---

## 1. Executive Summary
Traditional algorithmic trading bots rely on rigid static heuristics, while naive LLM trading wrappers suffer from severe hallucination and unconstrained drawdown risks. This project bridges this gap by introducing an institutional-grade, autonomous quantitative trading system. It decouples probabilistic LLM strategy reasoning (Google Gemini 3.6 Flash) from a 100% deterministic Python Hard Risk Gate, natively deployed across the Alpaca Trading API, Model Context Protocol (MCP) Server, Interactive CLI, and a Streamlit Execution Dashboard.

---

## 2. Core Architecture & Multi-Step Pipeline
The system operates as an isolated, deterministic-first quantitative pipeline:
1. **Market Data Fetcher**: Ingests historical daily bars and options chain snapshots via `alpaca-py` with dynamic Friday expiration calculations.
2. **Quantitative Regime Classifier**: Computes SMA 20/50, RSI 14, ATR 14, Realized Volatility %, and Bollinger Bandwidth % to classify market regime into 5 states: `BULLISH_TRENDING`, `BEARISH_TRENDING`, `HIGH_VOLATILITY`, `LOW_VOLATILITY`, and `SIDEWAYS_CONSOLIDATION`.
3. **AI Strategy Synthesizer**: Translates quantitative regime summaries into strict Pydantic v2 `TradeIntent` proposals:
   - **High Volatility**: Defined-risk Iron Condors and credit spreads (harvesting elevated implied volatility).
   - **Trending**: Defined-risk Bull Call / Bear Put Spreads.
   - **Sideways / Low Volatility**: Range-bound mean reversion and defined-risk swing setups.
4. **Deterministic Hard Risk Gate**: Zero-trust validation layer enforcing strict capital preservation in pure Python:
   - Max 5.0% account equity allocation per trade ($5,000 max risk on a $100,000 portfolio).
   - Absolute ban on naked short options (mandatory protective long wings).
   - Directional stop-loss sanity and liquid buying power validation.
5. **Execution & Telemetry Engine**: Formats options to official OCC standard symbology (e.g., `SPY   260925C00680000`) and dispatches paper orders to Alpaca.
6. **Position & Exit Monitor**: Continuous lifecycle tracking with automated Take-Profit (+50%) and Stop-Loss (-40%) liquidation.

---

## 3. Technology Integration
- **Alpaca Ecosystem**: Full utilization of Alpaca Trading API, Market Data API, and Paper Trading infrastructure ($100k starting balance).
- **FastMCP Server (`mcp_server/server.py`)**: Exposes 7 quantitative trading tools (`detect_market_regime`, `get_account_risk_summary`, `evaluate_risk_gate`, `generate_ai_strategy`, `execute_alpaca_order`, `monitor_and_liquidate_positions`, `run_autonomous_pipeline`) enabling standard LLM tool-calling interoperability.
- **Interactive CLI & Daemon (`cli.py`)**: Complete terminal-based scanner, manual inspection, and continuous background daemon (`python cli.py daemon --interval 60`).
- **Institutional Dashboard (`dashboard/app.py`)**: Streamlit web terminal featuring real-time account telemetry, interactive Plotly regime radar, and explainable AI audit logs.

---

**Repository URL**: `https://github.com/cybort18/alpaca-regime-options-agent.git`
