# Official System Rules & Hackathon Specification
## Alpaca AI Trading Agents Hackathon (LabLab.ai)

---

## 1. Hackathon Challenge Overview & Context
This project is built strictly to fulfill and excel in the **Alpaca AI Trading Agents Hackathon** hosted by **LabLab.ai** in partnership with **Alpaca**.

- **Competition Environment**: Alpaca Paper Trading Platform (Starting Balance: $100,000.00).
- **Core Objective**: Build an autonomous, production-grade AI trading agent that analyzes quantitative market signals, synthesizes strategic trade intents, executes trades via Alpaca infrastructure, and enforces institutional-grade risk management.
- **Evaluation Dimensions**:
  1. **P&L and Risk-Adjusted Performance**: Realized and unrealized returns generated in paper trading under disciplined capital management.
  2. **Technical Architecture & Originality**: Robustness of the multi-step isolated pipeline, deterministic risk guardrails, and explainability.
  3. **Alpaca Ecosystem Integration**: Comprehensive utilization of Alpaca Trading API, Model Context Protocol (MCP) server, and CLI tools.
  4. **Mandatory Options Integration**: Mandatory inclusion of defined-risk options strategies across trading workflows.

---

## 2. Required Technology Stack
- **Language**: Python 3.11+
- **Broker & Market Data**: Alpaca Trading & Market Data API via official `alpaca-py` SDK (`StockHistoricalDataClient`, `OptionHistoricalDataClient`, `TradingClient`).
- **AI / LLM Engine**: Google Gemini (official `google-genai` SDK with active model `gemini-3.6-flash`).
- **Protocol Standards**: Model Context Protocol (FastMCP / MCP 2.x standard JSON-RPC over stdio).
- **Data Validation & Schemas**: Pydantic v2 (`TradeIntent`, `OptionLeg`, `MarketRegime`, `InstrumentType`).
- **Quantitative Indicators**: Deterministic `pandas` and `numpy` (SMA 20/50, RSI 14, ATR 14, Realized Volatility, Bollinger Bandwidth).
- **User Interface**: Streamlit + Plotly (Institutional Dark Terminal Theme).
- **CLI Interface**: Python `argparse` with continuous background daemon support.

---

## 3. Non-Negotiable Architectural Guardrails

### Rule 1: Zero Direct LLM Broker Access (Isolated Multi-Step Pipeline)
- The Large Language Model (LLM) **NEVER** interacts directly with the Alpaca broker API or submits raw orders.
- The LLM acts **strictly as an isolated quantitative strategy synthesizer**, consuming structured technical indicators (`summary_dict`) and outputting schema-validated JSON proposals (`TradeIntent`).
- No order can reach the execution engine without traversing the deterministic Risk Gate.

### Rule 2: 100% Deterministic Mathematical Risk Gate
The `RiskGate` module is written entirely in pure Python logic with **zero AI intervention** and enforces hard mathematical boundaries:
1. **Max Position Sizing**: Total cost or maximum potential risk per trade must **never exceed 5.0% of total account equity** ($5,000 max allocation on a $100,000 portfolio).
2. **Liquidity & Buying Power**: Trade allocation must not exceed available real-time cash and buying power.
3. **Account State Verification**: The Alpaca account must be `ACTIVE` and `trading_blocked == False`.
4. **Directional Sanity**:
   - For long orders: `stop_loss < entry_price` and `target_price > entry_price`.
   - For short/credit spreads: `stop_loss > entry_price` and `target_price < entry_price`.

### Rule 3: Mandatory Defined-Risk Options Architecture (No Naked Shorting)
- **Mandatory Options Trading**: As required by hackathon rules, options strategies must be integrated into the core decision matrix.
- **Strict Naked Option Prohibition**: Naked short options (uncovered sell legs) are **100% prohibited** at both Pydantic schema validation and Risk Gate evaluation levels.
- Every `SELL_TO_OPEN` leg **MUST** be paired with a corresponding protective `BUY_TO_OPEN` wing (e.g., Vertical Debit Spreads, Vertical Credit Spreads, or 4-Leg Iron Condors).

### Rule 4: Dynamic Quantitative Regime Mapping
The strategy agent must dynamically align proposed trades with the 5 quantitative market regimes:

| Detected Market Regime | Technical Trigger Criteria | Mandated AI Strategy | Instrument Type |
| :--- | :--- | :--- | :--- |
| **BULLISH_TRENDING** | Price > SMA20 > SMA50, RSI in (50, 75), positive slope | **Bull Call Spread** / **Long Equity** | OPTION / EQUITY |
| **BEARISH_TRENDING** | Price < SMA20 < SMA50, RSI in (25, 50), negative slope | **Bear Put Spread** / **Long Put** | OPTION |
| **HIGH_VOLATILITY** | Realized Volatility > 25% or ATR% > 2.5% | **Iron Condor** / **Credit Spread** | OPTION |
| **SIDEWAYS_CONSOLIDATION** | Price oscillating between SMA20/50, BB Bandwidth < 6% | **Range Swing Trade** / **Neutral Spread** | EQUITY / OPTION |
| **LOW_VOLATILITY** | Realized Volatility < 12%, ATR% < 1.0%, BB Squeeze | **Range Bound Spread** / **Breakout Long** | OPTION / EQUITY |

### Rule 5: Standardized Friday Expirations & OCC Notation
- To guarantee that options contracts are actively listed and liquid on US exchanges, option expiration dates must strictly fall on **valid upcoming Fridays** (2 to 6 weeks out).
- Option symbols must be formatted in strict compliance with the **OCC Option Symbol Standard**:
  `[TICKER (6 chars, right-padded)] + [YYMMDD (6 digits)] + [C/P (1 char)] + [STRIKE * 1000 (8 digits)]`
  *(Example: `SPY   260925C00680000`)*.

### Rule 6: Autonomous Position Lifecycle & Exit Engine
- Open positions must be continuously monitored against explicit exit rules:
  - **Take Profit**: Automatic liquidation when unrealized P&L reaches **+50.0%**.
  - **Hard Stop Loss**: Automatic liquidation when unrealized loss reaches **-40.0%**.
  - **Hold**: Positions within risk boundaries remain active until exit criteria or options expiration.

---

## 4. Code Quality, Security & Presentation Standards

1. **Security & Secrets Management**:
   - Real API keys and credentials must **never** be hardcoded or committed to git.
   - `.env` must remain strictly ignored by `.gitignore`.
   - `.env.example` must be maintained with safe placeholder templates.
2. **Professional Institutional Aesthetics**:
   - Code comments, docstrings, CLI output, and web dashboard must adhere to clean, institutional Bloomberg/BlackRock terminal aesthetics.
   - Gratuitous emojis or "AI-slop vibe coding" are strictly prohibited in user-facing and production files.
3. **Resilience & Fault Tolerance**:
   - Network timeouts and DNS interception must be handled gracefully with synthetic fallback mechanisms for offline testing and dry-run execution.
   - CLI tools and background daemon loops must support clean, instant shutdown on `Ctrl + C` without raw Python tracebacks.

---

## 5. Submission Checklist & Deliverables

- [x] Functional multi-step trading pipeline with 100% test pass rate.
- [x] Integration with Alpaca Trading & Market Data API.
- [x] Defined-risk options strategy generation (Bull Call, Bear Put, Iron Condor).
- [x] Deterministic 5.0% equity Risk Gate.
- [x] FastMCP Server exposing 7 quantitative tools (`mcp_server/server.py`).
- [x] Command Line Interface with continuous daemon support (`cli.py`).
- [x] Interactive Streamlit & Plotly Dashboard (`dashboard/app.py`).
- [x] Dedicated 1-page competition write-up (`SUBMISSION_WRITEUP.md`).
- [x] Public GitHub repository with clean history and documentation (`README.md`).