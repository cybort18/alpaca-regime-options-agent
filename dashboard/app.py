import os
import sys
import json
from pathlib import Path
from datetime import datetime, date
from dataclasses import dataclass
from typing import Optional

# Ensure project root is in sys.path regardless of execution directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from dotenv import load_dotenv

from schemas.trade_intent import MarketRegime, InstrumentType, OptionAction
from data.market_fetcher import MarketDataFetcher
from analysis.regime_detector import RegimeDetector
from agent.strategy_agent import StrategyAgent
from risk.risk_gate import RiskGate
from execution.alpaca_executor import AlpacaExecutor
from execution.position_monitor import PositionMonitor
from scheduler.autonomous_runner import AutonomousRunner

# -----------------------------------------------------------------------------
# Page Configuration & Institutional Theme (No Emojis, Clean Monochrome / Accent)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Alpaca Regime-Aware Options Agent",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Professional Institutional Trading Terminal Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    code, pre, .terminal-text {
        font-family: 'JetBrains Mono', monospace !important;
    }

    .main { 
        background-color: #0d1117; 
        color: #c9d1d9;
    }
    
    .stMetric {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 16px;
        border-radius: 6px;
    }
    
    .regime-badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 4px;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 600;
        font-size: 0.78rem;
        letter-spacing: 0.5px;
    }
    .badge-bullish { background-color: rgba(46, 160, 67, 0.15); color: #3fb950; border: 1px solid #2ea043; }
    .badge-bearish { background-color: rgba(248, 81, 73, 0.15); color: #f85149; border: 1px solid #da3633; }
    .badge-volatile { background-color: rgba(210, 153, 34, 0.15); color: #d29922; border: 1px solid #bb8009; }
    .badge-sideways { background-color: rgba(88, 166, 255, 0.15); color: #58a6ff; border: 1px solid #388bfd; }
    .badge-lowvol { background-color: rgba(187, 128, 255, 0.15); color: #bc8cff; border: 1px solid #8957e5; }

    .audit-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .approved-tag { color: #3fb950; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
    .rejected-tag { color: #f85149; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Initialize Components & Session State
# -----------------------------------------------------------------------------
load_dotenv()

if "audit_history" not in st.session_state:
    st.session_state.audit_history = []

if "latest_cycle_report" not in st.session_state:
    st.session_state.latest_cycle_report = None

if "radar_data" not in st.session_state:
    st.session_state.radar_data = {}


@st.cache_resource
def get_pipeline_components():
    fetcher = MarketDataFetcher()
    detector = RegimeDetector()
    agent = StrategyAgent()
    gate = RiskGate(max_position_size_pct=0.05)
    executor = AlpacaExecutor()
    monitor = PositionMonitor(profit_target_pct=0.50, stop_loss_pct=0.40)
    return fetcher, detector, agent, gate, executor, monitor


fetcher, detector, agent, gate, executor, monitor = get_pipeline_components()

# -----------------------------------------------------------------------------
# Live Account Snapshot & Connectivity
# -----------------------------------------------------------------------------
@dataclass
class AccountSnapshot:
    equity: float = 100_000.0
    buying_power: float = 200_000.0
    cash: float = 50_000.0
    status: str = "ACTIVE"
    trading_blocked: bool = False


try:
    account = gate.get_account()
    equity = float(account.equity)
    buying_power = float(account.buying_power)
    cash = float(account.cash)
    status = str(account.status).upper()
    active_account = account
    is_live_account = True
    account_mode_label = "ALPACA LIVE PAPER"
except Exception:
    active_account = AccountSnapshot()
    equity = active_account.equity
    buying_power = active_account.buying_power
    cash = active_account.cash
    status = "ACTIVE"
    is_live_account = False
    account_mode_label = "OFFLINE SIMULATION"

# -----------------------------------------------------------------------------
# Sidebar: System Controls & Configuration
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### System Control Panel")
    st.caption(f"Environment: **{account_mode_label}**")
    
    st.markdown("---")
    st.markdown("#### Engine Configuration")
    model_choice = st.selectbox(
        "AI Strategy Model",
        ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"],
        index=0
    )
    agent.model_name = model_choice

    watchlist_input = st.multiselect(
        "Watchlist Symbols",
        options=["SPY", "AAPL", "NVDA", "QQQ", "MSFT", "TSLA", "AMD", "IWM"],
        default=["SPY", "AAPL", "NVDA", "QQQ", "MSFT"],
    )

    max_positions = st.slider("Max Concurrent Positions", min_value=1, max_value=10, value=5)
    dry_run_toggle = st.toggle("Dry-Run Execution Mode", value=True, help="Simulate order submission without altering live paper account balance.")

    st.markdown("---")
    st.markdown("#### Autonomous Execution")

    if st.button("Trigger Autonomous Scan Cycle", type="primary", use_container_width=True):
        with st.spinner("Executing full pipeline across watchlist assets..."):
            runner = AutonomousRunner(
                watchlist=watchlist_input,
                max_open_positions=max_positions,
                dry_run=dry_run_toggle,
                fetcher=fetcher,
                detector=detector,
                agent=agent,
                gate=gate,
                executor=executor,
                monitor=monitor,
            )
            report = runner.run_iteration(account_override=active_account)
            st.session_state.latest_cycle_report = report

            # Update Audit History
            for order in report.get("new_orders_submitted", []):
                st.session_state.audit_history.insert(0, {
                    "timestamp": report["timestamp"],
                    "symbol": order["symbol"],
                    "strategy": order["strategy"],
                    "instrument_type": order["instrument_type"],
                    "details": order["execution"],
                    "verdict": "APPROVED",
                })
            for rej in report.get("rejected_or_failed", []):
                st.session_state.audit_history.insert(0, {
                    "timestamp": report["timestamp"],
                    "symbol": rej.get("symbol", "N/A"),
                    "strategy": rej.get("strategy", "N/A"),
                    "reasons": rej.get("reasons", [rej.get("error", "Unknown error")]),
                    "verdict": "REJECTED",
                })
            st.success("Autonomous cycle completed.")

    st.markdown("---")
    st.markdown("#### Risk Gate Specifications")
    st.caption("• Max Allocation per Trade: <= 5.0% Total Equity")
    st.caption("• Defined-Risk Options Spreads: 100% Enforced")
    st.caption("• Profit Target: +50% | Hard Stop Loss: -40%")
    st.caption("• AI Access: Structured JSON Proposals Only")

# -----------------------------------------------------------------------------
# Main Header & Institutional KPI Bar
# -----------------------------------------------------------------------------
st.markdown("## Alpaca Regime-Aware AI Trading Agent")
st.caption("Quantitative Multi-Regime Options Engine • Deterministic Hard Risk Gate • Autonomous Execution")

positions_list = monitor.get_open_positions()
open_pos_count = len(positions_list) if positions_list else 0

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
with kpi1:
    st.metric("Total Equity", f"${equity:,.2f}")
with kpi2:
    st.metric("Buying Power", f"${buying_power:,.2f}")
with kpi3:
    st.metric("Cash Balance", f"${cash:,.2f}")
with kpi4:
    st.metric("Active Positions", f"{open_pos_count} / {max_positions}")
with kpi5:
    st.metric("Connection Status", "ONLINE" if is_live_account else "SIMULATION")

st.markdown("---")

# -----------------------------------------------------------------------------
# Main Content Tabs
# -----------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "Market Regime Radar",
    "AI Reasoning & Risk Gate Audit Log",
    "Active Positions & Risk Monitor",
    "Pipeline Telemetry Log",
])

# -----------------------------------------------------------------------------
# TAB 1: Market Regime Radar
# -----------------------------------------------------------------------------
with tab1:
    st.markdown("### Market Regime Radar")
    st.caption("Real-time deterministic technical indicator analysis and market regime classification.")

    radar_rows = []
    for sym in watchlist_input:
        try:
            bars = fetcher.get_daily_bars(sym, days=60)
            analysis = detector.analyze(sym, bars)
            st.session_state.radar_data[sym] = {"bars": bars, "analysis": analysis}

            regime_val = analysis.detected_regime.value
            badge_class = "badge-bullish" if "BULLISH" in regime_val else (
                "badge-bearish" if "BEARISH" in regime_val else (
                    "badge-volatile" if "HIGH_VOL" in regime_val else "badge-sideways"
                )
            )

            radar_rows.append({
                "Symbol": sym,
                "Last Price": f"${analysis.last_close:.2f}",
                "Market Regime": f"<span class='regime-badge {badge_class}'>{regime_val}</span>",
                "Confidence": f"{analysis.confidence * 100:.0f}%",
                "RSI (14)": f"{analysis.rsi_14:.1f}",
                "SMA (20 / 50)": f"${analysis.sma_20:.1f} / ${analysis.sma_50:.1f}",
                "ATR (14)": f"${analysis.atr_14:.2f} ({analysis.summary_dict.get('atr_pct', 0):.1f}%)",
                "Realized Vol": f"{analysis.realized_volatility:.1f}%",
            })
        except Exception as e:
            st.error(f"Error analyzing {sym}: {e}")

    if radar_rows:
        radar_df = pd.DataFrame(radar_rows)
        st.write(radar_df.to_html(escape=False, index=False), unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Technical Indicator Chart")
    selected_chart_sym = st.selectbox("Select Symbol to Inspect", watchlist_input, index=0)
    
    if selected_chart_sym in st.session_state.radar_data:
        chart_data = st.session_state.radar_data[selected_chart_sym]
        bars_df = chart_data["bars"]
        indicators_df = detector.compute_indicators(bars_df)

        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=indicators_df["timestamp"],
            open=indicators_df["open"],
            high=indicators_df["high"],
            low=indicators_df["low"],
            close=indicators_df["close"],
            name="OHLC Price",
        ))
        fig.add_trace(go.Scatter(
            x=indicators_df["timestamp"],
            y=indicators_df["sma_fast"],
            line=dict(color="#58a6ff", width=1.5),
            name="SMA 20",
        ))
        fig.add_trace(go.Scatter(
            x=indicators_df["timestamp"],
            y=indicators_df["sma_slow"],
            line=dict(color="#d29922", width=1.5),
            name="SMA 50",
        ))
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0d1117",
            plot_bgcolor="#161b22",
            height=400,
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# TAB 2: AI Reasoning & Risk Gate Audit Log (Explainable AI)
# -----------------------------------------------------------------------------
with tab2:
    st.markdown("### Explainable AI & Deterministic Risk Audit")
    st.caption("Auditable trail of LLM quantitative reasoning and mathematical risk gate compliance checks.")

    if not st.session_state.audit_history:
        st.info("No proposals logged yet. Click 'Trigger Autonomous Scan Cycle' in the sidebar to execute.")
    else:
        for idx, audit in enumerate(st.session_state.audit_history):
            with st.container():
                verdict = audit.get("verdict", "APPROVED")
                tag_html = f"<span class='approved-tag'>[APPROVED BY RISK GATE]</span>" if verdict == "APPROVED" else f"<span class='rejected-tag'>[REJECTED BY RISK GATE]</span>"
                
                st.markdown(f"""
                <div class="audit-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:1.05rem; font-weight:600;">{audit['symbol']} | Strategy: {audit.get('strategy', 'N/A')}</span>
                        <div>{tag_html}</div>
                    </div>
                    <div style="color:#8b949e; font-size:0.8rem; margin-top:4px; font-family:'JetBrains Mono';">TIMESTAMP: {audit.get('timestamp')}</div>
                </div>
                """, unsafe_allow_html=True)

                col_a, col_b = st.columns([3, 2])
                with col_a:
                    st.markdown("**Quantitative Reasoning:**")
                    details = audit.get("details", {})
                    reasoning = details.get("reasoning", "Detailed rationale recorded during pipeline execution.")
                    st.markdown(f"> {reasoning}")

                    if "legs" in details and details["legs"]:
                        st.markdown("**Option Spread Legs:**")
                        legs_df = pd.DataFrame(details["legs"])
                        st.dataframe(legs_df, use_container_width=True, hide_index=True)

                with col_b:
                    st.markdown("**Risk Gate Verification:**")
                    if verdict == "APPROVED":
                        st.success("Passed: Position Allocation <= 5.0% Equity\n\nPassed: Sufficient Buying Power Available\n\nPassed: Defined-Risk Leg Protection Verified")
                    else:
                        reasons = audit.get("reasons", ["Risk check failed"])
                        for r in reasons:
                            st.error(f"Failed: {r}")

                st.markdown("---")

# -----------------------------------------------------------------------------
# TAB 3: Active Positions & Risk Monitor
# -----------------------------------------------------------------------------
with tab3:
    st.markdown("### Active Positions & Risk Monitor")
    st.caption("Real-time position monitoring with automated liquidation at +50% Profit Target or -40% Stop Loss.")

    if not positions_list:
        st.info("No active open positions in the Alpaca account.")
    else:
        pos_data = []
        for pos in positions_list:
            sym = getattr(pos, "symbol", "N/A")
            qty = float(getattr(pos, "qty", 0))
            entry = float(getattr(pos, "avg_entry_price", 0))
            curr = float(getattr(pos, "current_price", 0))
            pnl_usd = float(getattr(pos, "unrealized_pl", 0))
            pnl_pct = float(getattr(pos, "unrealized_plpc", 0)) * 100

            status_label = "[TAKE PROFIT TARGET]" if pnl_pct >= 50 else ("[STOP LOSS TRIGGER]" if pnl_pct <= -40 else "[HOLD - WITHIN RISK]")

            pos_data.append({
                "Symbol": sym,
                "Quantity": qty,
                "Entry Price": f"${entry:.2f}",
                "Current Price": f"${curr:.2f}",
                "Unrealized P&L ($)": f"${pnl_usd:+,.2f}",
                "Unrealized P&L (%)": f"{pnl_pct:+.2f}%",
                "Action Status": status_label,
            })

        st.dataframe(pd.DataFrame(pos_data), use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# TAB 4: Pipeline Execution Summary
# -----------------------------------------------------------------------------
with tab4:
    st.markdown("### Latest Pipeline Telemetry")
    if st.session_state.latest_cycle_report:
        st.json(st.session_state.latest_cycle_report)
    else:
        st.info("No telemetry logs available. Trigger a scan cycle to inspect raw JSON output.")
