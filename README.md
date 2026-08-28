# Alpaca Regime-Aware Options and Equity Trading Agent

An autonomous, multi-step algorithmic trading pipeline that combines technical market regime detection, AI-formulated trade proposals, a 100% deterministic hard risk gate, automated position management, and order execution via the Alpaca Trading API.

---

## Core Architecture and Guardrails

This project enforces strict security and risk-management boundaries:

1. **AI Output Isolation**: The AI/LLM never interacts with the broker or executes trades directly. It only outputs structured JSON trade proposals conforming to the strict Pydantic `TradeIntent` schema.
2. **Deterministic Hard Risk Gate**: All proposals must pass a 100% deterministic Python risk gate before orders can be submitted:
   - Position sizing capped at a maximum of 5% of total account equity.
   - Strict validation of available buying power and cash.
   - Defined-risk enforcement: naked short options are strictly prohibited (every short leg must be covered by a protective long leg).
   - Sanity checks on target profit and stop-loss levels relative to entry price and order direction.
3. **Regime-Aware Strategy Mapping**: Strategies are tailored dynamically to detected market regimes (Bull Call Spreads, Bear Put Spreads, Iron Condors, and Range-bound Equity trades).

---

## Multi-Step Pipeline Flow

```
[ Market Data Fetcher ]
         |
         v
[ Technical Regime Detector ] (SMA 20/50, RSI 14, ATR 14, Realized Volatility)
         |
         v
[ AI Strategy Agent ] (Formulates TradeIntent JSON proposal)
         |
         v
[ Deterministic Hard Risk Gate ] (5% Equity Cap, Buying Power, Defined Risk)
         |
         +--> [ Rejected ] -> Log & Discard
         |
         v
[ Alpaca Order Executor ] (OCC Option Symbol conversion & Order submission)
         |
         v
[ Position Monitor & Exit Engine ] (Monitors Unrealized PnL, Auto Take-Profit / Stop-Loss)
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
│   └── strategy_agent.py       # AI prompt engine & regime strategy synthesizer
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
*(Or install core dependencies directly: `pip install alpaca-py pydantic pandas numpy openai python-dotenv`)*

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
OPENAI_API_KEY=your_openai_api_key_here
```

---

## Running Automated Tests

Run the complete test suite to verify all modules:

```bash
# 1. Test Pydantic Schemas & Deterministic Risk Gate
python test_modules.py

# 2. Test Market Data Fetching & Regime Detection
python test_market_analysis.py

# 3. Test End-to-End Multi-Step Pipeline
python test_pipeline_e2e.py

# 4. Test Position Monitor & Autonomous Runner
python test_runner.py
```

---

## Usage: Running the Autonomous Trading Agent

To run a single cycle scan across the watchlist:

```python
from scheduler.autonomous_runner import AutonomousRunner

runner = AutonomousRunner(
    watchlist=["SPY", "AAPL", "NVDA", "QQQ", "MSFT"],
    max_open_positions=5,
    dry_run=True,  # Set to False for live paper execution
)

report = runner.run_iteration()
print(report)
```

To run continuously as a scheduled background daemon:

```python
runner.run_loop(max_iterations=None)
```

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

## License

MIT License.
