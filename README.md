# Alpaca Regime-Aware Options and Equity Autonomous Trading Agent

An autonomous, production-grade algorithmic trading system that combines technical market regime detection, Google Gemini quantitative reasoning, a 100% deterministic mathematical risk gate, Model Context Protocol (MCP) tool server, interactive CLI, and Streamlit execution telemetry dashboard via the Alpaca Trading API.

Built for the Alpaca AI Trading Agents Hackathon on LabLab.ai.

---

## Core System Architecture & Guardrails

This project enforces strict security and risk-management boundaries:

1. **AI Output Isolation**: The AI/LLM never interacts with the broker or executes trades directly. It only outputs structured JSON trade proposals conforming to the strict Pydantic `TradeIntent` schema.
2. **Deterministic Hard Risk Gate**: All proposals must pass a 100% deterministic Python risk gate before orders can be submitted:
   - Position sizing capped at a maximum of 5.0% of total account equity.
   - Strict validation of available buying power and cash.
   - Defined-risk enforcement: naked short options are strictly prohibited (every short leg must be covered by a protective long leg).
   - Sanity checks on target profit and stop-loss levels relative to entry price and order direction.
3. **Regime-Aware Strategy Mapping**: Strategies are tailored dynamically to detected market regimes (Bull Call Spreads, Bear Put Spreads, Iron Condors, and Range-bound Equity trades).
4. **Model Context Protocol (MCP) Integration**: Official FastMCP server exposes quantitative tools for external agentic orchestration and multi-agent systems.

---

## Multi-Step Pipeline Flow

```
[ Market Data Fetcher ]
         |
         v
[ Technical Regime Detector ] (SMA 20/50, RSI 14, ATR 14, Realized Volatility)
         |
         v
[ AI Strategy Agent ] (Google Gemini Model -> Formulates TradeIntent JSON proposal)
         |
         v
[ Deterministic Hard Risk Gate ] (5.0% Equity Cap, Buying Power, Defined Risk)
         |
         +--> [ Rejected ] -> Log & Discard
         |
         v
[ Alpaca Order Executor ] (OCC Option Symbol conversion & Order submission)
         |
         v
[ Position Monitor & Exit Engine ] (Monitors Unrealized PnL, Auto Take-Profit / Stop-Loss)
         |
         v
[ Telemetry & Visualization ] (Streamlit Dashboard, CLI, & MCP Server)
```

---

## Project Structure

```text
ALPACA AI Trading/
├── .env.example                # Template for environment variables
├── .gitignore                  # Git ignore configuration
├── PROJECT_RULES.md            # Non-negotiable architectural rules
├── PROJECT_SUMMARY.md          # Comprehensive technical report
├── README.md                   # Project documentation
├── requirements.txt            # Project dependencies
├── cli.py                      # Interactive Command-Line Interface (Alpaca CLI)
│
├── schemas/
│   ├── __init__.py
│   └── trade_intent.py         # Pydantic v2 schemas (TradeIntent, OptionLeg, MarketRegime)
│
├── risk/
│   ├── __init__.py
│   └── risk_gate.py            # 100% deterministic hard risk gate
│
├── data/
│   ├── __init__.py
│   └── market_fetcher.py       # Alpaca historical daily bars & option chain client
│
├── analysis/
│   ├── __init__.py
│   └── regime_detector.py      # Technical indicator engine & market regime classifier
│
├── agent/
│   ├── __init__.py
│   └── strategy_agent.py       # Google Gemini AI prompt engine & regime strategy synthesizer
│
├── execution/
│   ├── __init__.py
│   ├── alpaca_executor.py      # Alpaca order execution & OCC symbol formatter
│   └── position_monitor.py     # Position monitor & auto-exit liquidation engine
│
├── scheduler/
│   ├── __init__.py
│   └── autonomous_runner.py    # Autonomous watchlist scanner & continuous loop runner
│
├── mcp_server/
│   ├── __init__.py
│   └── server.py               # Model Context Protocol (MCP) tool server
│
├── dashboard/
│   ├── __init__.py
│   └── app.py                  # Streamlit execution dashboard & explainability UI
│
├── test_modules.py             # Unit tests for Schemas and RiskGate
├── test_market_analysis.py     # Tests for Market Data Fetcher and Regime Detector
├── test_pipeline_e2e.py        # End-to-End integration pipeline tests
└── test_runner.py              # Tests for Position Monitor & Autonomous Runner
```

---

## Installation and Setup

### 1. Prerequisites
- Python 3.11 or higher
- Alpaca Trading account (Paper or Live)
- Google Gemini API Key

### 2. Clone Repository and Set Up Virtual Environment

```bash
git clone https://github.com/cybort18/alpaca-regime-options-agent.git
cd alpaca-regime-options-agent

python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_SECRET_KEY=your_alpaca_secret_key_here
ALPACA_PAPER=True
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

---

## Usage: CLI, Web Dashboard, and MCP Server

### 1. Interactive Command Line Interface (CLI)

```bash
# Run autonomous watchlist scan
python cli.py scan --symbols SPY,AAPL,NVDA,QQQ,MSFT --max-pos 5

# Inspect market regime and technical indicators for a ticker
python cli.py regime SPY

# Generate AI trade strategy proposal via Gemini
python cli.py strategy AAPL

# Inspect open positions and exit status
python cli.py positions

# Run full test suite
python cli.py test

# Launch MCP Tool Server
python cli.py mcp
```

### 2. Interactive Web Dashboard

```bash
streamlit run dashboard/app.py
```
Open `http://localhost:8501` to view:
- Live Account KPI Bar (Equity, Buying Power, Cash, Positions).
- Market Regime Radar & Plotly Technical Candlestick Charts.
- Explainable AI Reasoning & Risk Gate Audit Trail.
- Active Positions & Take-Profit / Stop-Loss Progress.

### 3. Model Context Protocol (MCP) Server

```bash
python -m mcp_server.server
```
Exposes tools over standard MCP JSON-RPC protocol:
- `detect_market_regime`
- `get_account_risk_summary`
- `evaluate_risk_gate`
- `generate_ai_strategy`
- `execute_alpaca_order`
- `monitor_and_liquidate_positions`
- `run_autonomous_pipeline`

---

## Strategy Mapping Reference

| Market Regime | Primary Strategy | Instrument | Risk Profile |
| :--- | :--- | :--- | :--- |
| BULLISH_TRENDING | Bull Call Spread / Long Equity | OPTION / EQUITY | Defined Risk (Debit Spread) |
| BEARISH_TRENDING | Bear Put Spread / Long Put | OPTION | Defined Risk (Debit Spread) |
| HIGH_VOLATILITY | Iron Condor / Credit Spread | OPTION | Defined Risk (Wing-Protected) |
| SIDEWAYS_CONSOLIDATION | Range Swing Trade | EQUITY / OPTION | Defined Risk (Channel Bounds) |
| LOW_VOLATILITY | Range Trade / Squeeze Breakout | EQUITY / OPTION | Defined Risk (Tight Stop Loss) |

---

## Automated Test Verification

Run all test suites:

```bash
python test_modules.py
python test_market_analysis.py
python test_pipeline_e2e.py
python test_runner.py
```

---

## License

MIT License.
