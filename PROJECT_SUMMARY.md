# Executive Summary & Technical Architecture Report
## Alpaca Regime-Aware AI Options & Equity Trading System

---

## 1. Ikhtisar Proyek (Project Overview)
Proyek ini membangun sistem trading kuantitatif terotomatisasi berbasis AI yang mengintegrasikan analisis data pasar historis, klasifikasi *market regime* (regim pasar), perumusan strategi trading oleh Large Language Model (LLM Google Gemini 2.5 Flash), gerbang risiko deterministik (*Hard Risk Gate*), eksekusi order ke broker **Alpaca Paper Trading**, manajemen posisi & *exit engine* otomatis, orkestrasi *autonomous runner* loop, serta **Interactive Streamlit Web Dashboard**.

Sistem dirancang dengan arsitektur **multi-step pipeline terisolasi** di mana kecerdasan buatan (LLM) **tidak pernah mengeksekusi order secara langsung**, melainkan hanya bertindak sebagai perumus proposal order terstruktur dalam format JSON yang wajib melewati validasi skema dan aturan gerbang risiko 100% deterministik.

---

## 2. Guardrails & Strict Rules (`PROJECT_RULES.md`)
Sistem tunduk pada aturan ketat yang tidak dapat dinegosiasikan (*non-negotiable safety guardrails*):

1. **AI Output Isolate**: LLM HANYA menghasilkan proposal berformat JSON tervalidasi skema Pydantic (`TradeIntent`). LLM tidak memiliki akses langsung untuk menempatkan order ke broker.
2. **Deterministic Hard Risk Gate**: Modul `RiskGate` adalah 100% kode Python deterministik murni tanpa intervensi AI. Modul ini mengevaluasi:
   - Alokasi biaya/risiko per posisi $\le 5\%$ dari total *equity* akun Alpaca.
   - Ketersediaan *buying power* / kas.
   - Kewajaran *stop-loss* dan *target price*.
   - Larangan keras terhadap *naked short options* (setiap posisi *sell* opsi wajib memiliki kaki proteksi *buy* / *defined risk*).
3. **Regime-Aware Strategy Mapping**: Setiap keputusan order (Opsi / Ekuitas) disesuaikan secara dinamis dengan regim pasar yang terdeteksi.

---

## 3. Diagram Alur Sistem (End-to-End Pipeline)

```mermaid
flowchart TD
    subgraph S["Autonomous Runner & Dashboard (dashboard/app.py)"]
        A1[Scan Open Positions] --> A2{position_monitor.py}
        A2 -- Take Profit / Stop Loss --> A3[Liquidate / Close Position]
        A2 -- Healthy --> A4[Hold Position]
        A3 --> B1[Calculate Available Portfolio Slots]
        A4 --> B1
        B1 --> B2[Scan Watchlist: SPY, AAPL, NVDA, QQQ, MSFT]
        B2 -->|Candidate Symbol| C1(data/market_fetcher.py)
        C1 -->|Daily OHLCV Bars| C2(analysis/regime_detector.py)
        C2 -->|Indicators & MarketRegime| C3(agent/strategy_agent.py)
        C3 -->|TradeIntent JSON (Gemini 2.5 Flash)| C4{risk/risk_gate.py}
        C4 -- Rejected --> C5[Log Rejection Reason]
        C4 -- Approved --> C6(execution/alpaca_executor.py)
        C6 -->|OCC Symbol / Order| C7[Alpaca Trading API]
    end
```

---

## 4. Rincian Modul & Arsitektur Kode

### A. Folder `schemas/`: Kontrak Data & Validasi Pydantic
- **[`schemas/trade_intent.py`](file:///c:/Users/HP/Documents/PROJECT/ALPACA%20AI%20Trading/schemas/trade_intent.py)**:
  - **`MarketRegime`** (Enum): `BULLISH_TRENDING`, `BEARISH_TRENDING`, `SIDEWAYS_CONSOLIDATION`, `HIGH_VOLATILITY`, `LOW_VOLATILITY`.
  - **`InstrumentType`** (Enum): `EQUITY`, `OPTION`.
  - **`OptionLeg`** (Model): Kaki kontrak opsi (`strike_price`, `expiration_date`, `option_type` [CALL/PUT], `action` [BUY_TO_OPEN/SELL_TO_OPEN], `quantity`).
  - **`TradeIntent`** (Model): Proposal order lengkap yang memuat `symbol`, `market_regime`, `instrument_type`, `strategy_name`, `action`, `quantity`, `estimated_entry_price`, `target_price`, `stop_loss`, `options_legs`, `reasoning`, dan `confidence_score`.

### B. Folder `risk/`: Gerbang Risiko Deterministik
- **[`risk/risk_gate.py`](file:///c:/Users/HP/Documents/PROJECT/ALPACA%20AI%20Trading/risk/risk_gate.py)**:
  - Mengambil data akun Alpaca (`equity`, `buying_power`, `status`, `trading_blocked`).
  - **Aturan Ukuran Posisi**: Memastikan `proposed_cost <= 0.05 * account_equity`.
  - **Aturan Likuiditas**: Memastikan `proposed_cost <= buying_power`.
  - **Validasi Stop-Loss**: Memastikan stop loss logis terhadap harga entry dan arah order.

### C. Folder `data/`: Pengambil Data Pasar
- **[`data/market_fetcher.py`](file:///c:/Users/HP/Documents/PROJECT/ALPACA%20AI%20Trading/data/market_fetcher.py)**:
  - Menggunakan `StockHistoricalDataClient` dan `OptionHistoricalDataClient` dari `alpaca-py`.
  - Mengambil data daily bars historis (30-60 hari) dan snapshot options chain dengan fitur *synthetic fallback bar generator*.

### D. Folder `analysis/`: Detektor Regim & Indikator Teknikal
- **[`analysis/regime_detector.py`](file:///c:/Users/HP/Documents/PROJECT/ALPACA%20AI%20Trading/analysis/regime_detector.py)**:
  - Menghitung indikator teknikal murni (`pandas` + `numpy`): `SMA 20/50`, `RSI 14`, `ATR 14`, `Realized Volatility %`, `Bollinger Bandwidth %`.
  - Mengklasifikasikan regim pasar dan menghasilkan payload `summary_dict` untuk diinjeksikan ke prompt AI.

### E. Folder `agent/`: AI Strategy Agent (Google Gemini)
- **[`agent/strategy_agent.py`](file:///c:/Users/HP/Documents/PROJECT/ALPACA%20AI%20Trading/agent/strategy_agent.py)**:
  - Menggunakan SDK resmi `google-genai` dengan model default `gemini-2.5-flash`.
  - Memandu LLM merumuskan strategi berbasis regime:
    - **`BULLISH_TRENDING`**: *Bull Call Spread*, *Long Call*, atau *Long Equity*.
    - **`BEARISH_TRENDING`**: *Bear Put Spread* atau *Long Put*.
    - **`HIGH_VOLATILITY`**: *Defined-Risk Iron Condor* atau *Credit Spreads*.
    - **`SIDEWAYS_CONSOLIDATION` / `LOW_VOLATILITY`**: *Range-Bound Swing Trade* atau *Defined-Risk Spreads*.

### F. Folder `execution/`: Engine Eksekusi & Pemantau Posisi
- **[`execution/alpaca_executor.py`](file:///c:/Users/HP/Documents/PROJECT/ALPACA%20AI%20Trading/execution/alpaca_executor.py)**:
  - Format simbol opsi standar **OCC Option Symbol** (misal: `SPY260927C00688000`).
  - Mengirim order ekuitas dan opsi multi-leg ke Alpaca Paper API.
- **[`execution/position_monitor.py`](file:///c:/Users/HP/Documents/PROJECT/ALPACA%20AI%20Trading/execution/position_monitor.py)**:
  - Memantau seluruh posisi terbuka secara real-time.
  - Mengevaluasi unrealized P&L (% dan nominal).
  - Melakukan auto-liquidate ketika profit menyentuh target (+50%) atau stop loss (-40%).

### G. Folder `scheduler/`: Autonomous Runner
- **[`scheduler/autonomous_runner.py`](file:///c:/Users/HP/Documents/PROJECT/ALPACA%20AI%20Trading/scheduler/autonomous_runner.py)**:
  - Loop orkestrasi otomatis:
    1. Scan posisi terbuka & eksekusi Exit Signal jika tercapai.
    2. Cek kapasitas portofolio dan *buying power*.
    3. Pindai watchlist simbol (`SPY`, `AAPL`, `NVDA`, `QQQ`, `MSFT`) yang belum memiliki posisi aktif.
    4. Jalankan pipeline lengkap (Data $\rightarrow$ Regime $\rightarrow$ Strategy $\rightarrow$ Risk Gate $\rightarrow$ Execute).

### H. Folder `dashboard/`: Interactive Streamlit Web UI
- **[`dashboard/app.py`](file:///c:/Users/HP/Documents/PROJECT/ALPACA%20AI%20Trading/dashboard/app.py)**:
  - Dashboard modern dengan tema dark glassmorphism.
  - Menampilkan KPI bar akun, Market Regime Radar interaktif, kartu Explainable AI, pemantauan posisi & risiko, serta kontrol eksekusi otonom.

---

## 5. Struktur Direktori Lengkap

```text
ALPACA AI Trading/
├── .env                        # Konfigurasi API Key Alpaca & Gemini API
├── .env.example                # Template konfigurasi environment yang aman
├── .gitignore                  # Konfigurasi proteksi file secrets & temporary
├── PROJECT_RULES.md            # Aturan non-negotiable arsitektur sistem
├── PROJECT_SUMMARY.md          # Dokumen ringkasan lengkap ini
├── README.md                   # Dokumentasi resmi repositori
├── requirements.txt            # Dependensi proyek
│
├── schemas/
│   ├── __init__.py
│   └── trade_intent.py         # Skema Pydantic v2 TradeIntent & OptionLeg
│
├── risk/
│   ├── __init__.py
│   └── risk_gate.py            # Hard Risk Gate 100% deterministik (5% limit, BP, dsb.)
│
├── data/
│   ├── __init__.py
│   └── market_fetcher.py       # Client pengambil data historis & options chain Alpaca
│
├── analysis/
│   ├── __init__.py
│   └── regime_detector.py      # Kalkulasi SMA/RSI/ATR & Klasifikasi Market Regime
│
├── agent/
│   ├── __init__.py
│   └── strategy_agent.py       # AI Prompt Generator & Gemini Strategy Synthesizer
│
├── execution/
│   ├── __init__.py
│   ├── alpaca_executor.py      # Alpaca Order Execution & OCC Symbol Formatter
│   └── position_monitor.py     # Position Monitor, Unrealized P&L & Auto-Exit Engine
│
├── scheduler/
│   ├── __init__.py
│   └── autonomous_runner.py    # Autonomous Watchlist Scan & Continuous Runner Loop
│
├── dashboard/
│   ├── __init__.py
│   └── app.py                  # Interactive Streamlit Web UI & Explainability Dashboard
│
├── test_modules.py             # Test Suite Section 1 (Schemas & Risk Gate)
├── test_market_analysis.py     # Test Suite Section 2 (Market Data & Regime Detection)
├── test_pipeline_e2e.py        # Test Suite Section 3 (End-to-End Multi-Step Pipeline)
└── test_runner.py              # Test Suite Section 4 (Position Monitor & Autonomous Runner)
```

---

## 6. Cara Menjalankan Dashboard
```bash
streamlit run dashboard/app.py
```
Akses di browser pada: `http://localhost:8501`.
