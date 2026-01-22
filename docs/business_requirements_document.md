# Business Requirement Document
## Financial Valuation Intelligence Platform

**Version:** 1.1 (Updated with Speed Pipeline Specs)  
**Status:** Final Draft  
**Scope:** Public Markets (Equity Valuation)

---

## 1. Executive Summary
The objective of this project is to democratize institutional-grade financial analysis. We are developing an intelligent **Financial Valuation Platform** that automates the calculation of **Intrinsic Value (NPV)** for publicly traded companies.

By synthesizing deeply audited historical data (Financial Statements) with real-time market signals (Stock Data), we provide investors, portfolio managers, and students with a "living" valuation model. This removes the manual labor of data extraction and formula maintenance, allowing stakeholders to focus on high-level investment decisions based on the **Discounted Cash Flow (DCF)** methodology.

---

## 2. Business Architecture Strategy
To ensure valuations are both fundamentally sound and market-responsive, the platform operates on a "**Hybrid Processing Model**" (Lambda Architecture). This separates the business logic into three distinct layers:

### Layer A: The "Fundamental Truth" Engine (Batch Analysis)
*   **Function**: Processes "Slow Data"—audited Annual (10-K) and Quarterly (10-Q) reports.
*   **Business Value**: Establishes the baseline health of the company by calculating true cash generation (Free Cash Flow) and solvency risks (Debt Loads), independent of daily market noise.
*   **Frequency**: Quarterly / Annually.

### Layer B: The "Market Pulse" Engine (Speed Pipeline)
*   **Function**: Processes "Fast Data"—Streaming Stock Quotes and Market Index (SPY) movements via Kafka & Spark Structured Streaming.
*   **Business Value**: Monitors the "**Cost of Capital**" and "**Sentiment**." Even if a company's cash flow is stable, the risk of owning it changes by the minute. This layer calculates Beta (Systematic Risk), Volatility, and Momentum dynamically.
*   **Frequency**: Near Real-Time (Sliding Window updates every 5 minutes).

### Layer C: The "Decision" Interface (Serving Layer)
*   **Function**: Merges Fundamental Truths with the Market Pulse.
*   **Business Value**: Outputs the final **Net Present Value (NPV)**, providing a clear signal: *"Is this healthy company currently trading at a discount?"*

---

## 3. Data Lineage & Business Definitions

### A. Assessing Company Health (Inputs from Financial Statements - Batch)
**Source**: SEC EDGAR / Financial Modeling Prep (FMP)

| Business Concept | Definition | Logic / Formula | Why it Matters |
| :--- | :--- | :--- | :--- |
| **Operating Cash Flow** | Cash generated from core operations. | Direct Extraction | Validates the core business model. |
| **CAPEX** | Cash spent maintaining assets. | Direct Extraction | Represents the cost to stay in business. |
| **Free Cash Flow (FCF)** | The Primary Output. Cash available to investors. | `Operating Cash - CAPEX` | The "Fuel" for the DCF model. |
| **Debt Load** | Total financial obligations. | `Short Term + Long Term Debt` | Determines bankruptcy risk. |
| **Interest Expense** | Annual cost of servicing debt. | Direct Extraction | Determines Cost of Debt ($R_d$). |
| **Tax Rate** | Corporate tax burden. | `Tax Paid / Pre-Tax Income` | Used for Tax Shield calculations. |

### B. Assessing Market Risk (Inputs from Streaming Data - Speed)
**Source**: Kafka Producer (Simulated/Live Market Feed)

| Business Concept | Definition | Logic / Formula | Why it Matters |
| :--- | :--- | :--- | :--- |
| **Real-Time Beta ($\beta$)** | Measure of Systematic Risk vs Market (SPY). | $\frac{Cov(Stock, Market)}{Var(Market)}$ | Adjusts the discount rate (WACC) based on live correlation. |
| **Volatility ($\sigma$)** | Measure of Price Uncertainty. | `StdDev(Returns)` over Window | Used for position sizing and confidence intervals. |
| **Momentum** | Measure of Trend Strength. | `Avg(Returns)` over Window | Acts as a "Go/No-Go" timing signal (Don't catch a falling knife). |
| **Cost of Equity ($R_e$)** | Shareholder expected return. | $R_f + \beta(R_m - R_f)$ | *Note: Risk-Free Rate ($R_f$) = 4.25%, Market Risk Premium = 5.00% (MVP).* |

---

## 4. Speed Pipeline: Constraints & Business Logic
This section defines the specific constraints encountered during the development of the Streaming Layer and the business rules established to handle them.

### A. The "Sample Size" Constraint (Statistical Significance)
*   **Constraint**: Data arrives at a frequency of ~3 minutes per tick. A standard 10-minute window would only capture ~3 data points, rendering statistical metrics (Beta/Volatility) mathematically unstable.
*   **Business Rule**: To ensure statistical validity (Sample Size $n \approx 40$), the system enforces a **2-Hour Sliding Window**.
*   **Refresh Rate**: While the window looks back 2 hours, the calculation refreshes every **5 minutes** to provide timely updates.

### B. The "Frozen Market" Handling (Zero Variance)
*   **Constraint**: During after-hours trading, weekends, or periods of low liquidity, the Market Index (SPY) price may remain static for extended periods. This results in `Variance = 0`, causing "Division by Zero" errors in the Beta formula.
*   **Business Rule**:
    1.  **Strict Validation**: The system checks if `Market_Variance == 0`.
    2.  **Fail-Safe**: If Variance is 0, the system returns `NULL` (Undefined) for Beta rather than crashing or returning an infinite value.
    3.  **Fallback**: The Serving Layer must default to a Beta of 1.0 (Market Average) or the last known valid Beta if the real-time stream returns `NULL`.

### C. The "Source of Truth" for Time
*   **Constraint**: Producer-generated timestamps inside the JSON payload were found to be static/unreliable during testing.
*   **Business Rule**: The system strictly uses the **Kafka Ingestion Timestamp** (`timestamp` column) as the "Event Time" for all windowing operations. This ensures we measure "when the data arrived" rather than "when the faulty sensor claimed it happened."

---

## 5. Testing & Validation Strategy
We employ a "**Tiered Defense**" strategy to validate financial accuracy before deployment.

### Tier 1: Data Integrity (The Garbage Filter)
*   **Schema Enforcement**: Ensures incoming JSON matches the strict schema (Ticker, Price, Change%).
*   **Base64 Decoding**: Validates that incoming binary payloads can be successfully decoded to UTF-8 strings.

### Tier 2: Statistical Validity (The Stream Check)
*   **Minimum Sample Threshold**: The Streaming Engine discards any calculated Beta derived from fewer than **20 data points**. This prevents "Noise" from entering the Gold layer during system startup or connection drops.

### Tier 3: Market Calibration (The Truth Check)
*   **Benchmarking**:
    *   *Example*: We calculate MSFT Beta = 0.45. We check Yahoo Finance ("Benchmark") and see MSFT Beta = 0.89.
    *   **Logic**: Compare `Our_Beta` vs `Yahoo_Beta`.
    *   **Alert**: If difference > 5%, send email: *"Warning: Our model thinks MSFT is safe (0.45), but the market thinks it is risky (0.89). Check the data!"*
*   **Historical Backtesting**:
    *   **Goal**: Prove the algorithm makes money.
    *   **Process**: Feed 2023 data into the pipeline as if live. Calculate WACC and NPV.
    *   **Test**: If model signaled "BUY NVDA" in Jan 2023 (and stock rose 200%), PASS. If signaled "SELL", FAIL.

---

## 6. Strategic Vision & Roadmap
*   **Phase 0**: Introduce dynamic ingestion of daily Treasury Yield curves to automate $R_f$ adjustments.
*   **Phase 1**: US Blue Chip Tech (Completed).
*   **Phase 2**: Emerging Markets (Tunisia/BVMT) – Using OCR for non-API data.
*   **Phase 3**: Qualitative Risk – Integrating News Sentiment into WACC.
*   **Phase 4**: Platinum Layer (Scoring Engine): Implement a composite "Buy Score" that weights Fundamental NPV (60%), Momentum (20%), and Volatility Risk (20%) into a single decisional metric.
