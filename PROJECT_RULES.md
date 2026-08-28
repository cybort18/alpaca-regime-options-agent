# Alpaca Regime-Aware Options Trading Agent

## Tech Stack & Guardrails
- Language: Python 3.11+
- Execution: Alpaca Paper Trading SDK (`alpaca-py`) & MCP Tools
- Pattern: Multi-step pipeline (Market Analysis -> Regime Decision -> Hard Risk Gate -> Alpaca Order Execution)

## Strict Rules
1. LLM NEVER executes trades directly. LLM only outputs structured JSON proposals.
2. The `RiskGate` module is 100% deterministic Python rules (validates max position size <= 5% equity, buying power, stop-loss, and defined-risk options legs).
3. Every trade must support Options strategies (Spreads/Puts/Calls) or Equity hedging based on market regime.