# Technical Specification: Financial Cloud Engine

## 1. Conceptual Layer

### 1.1 Sources
*   **Financial Modeling Prep (FMP) API**: The primary source for fundamental data.
    *   **Endpoints**: Income Statement, Balance Sheet, Cash Flow Statement.
    *   **Frequency**: Quarterly (Periodicity).
*   **Finnhub API**: The primary source for market data.
    *   **Endpoints**: Stock Price, Market Status, Technical Indicators (Beta).
    *   **Frequency**: Real-time / High Frequency.

### 1.2 Data Nature
*   **Fundamental Data (Batch)**: Represents the "slow-moving" truth of a company's health. Examples: `Total Debt`, `Revenue`, `freeCashFlow`. This data is historical and immutable for a given quarter.
*   **Market Data (Stream)**: Represents the "fast-moving" sentiment of the market. Examples: `d` (Close Price), `beta` (Volatility). This data is ephemeral and continuous.

### 1.3 Extracted Entities & Meaning
| Entity | Source | Description | Business Meaning |
| :--- | :--- | :--- | :--- |
| **Income Statement** | FMP | Revenue, NOPAT, Tax Expense | Measures profitability and operating efficiency. |
| **Balance Sheet** | FMP | Total Debt, Cash, Assets | Measures financial health and leverage (Solvency). |
| **Cash Flow** | FMP | Operating/Investing CF | Measures liquidity and ability to fund operations. |
| **Ticker Data** | Finnhub | Price, Beta, Volatility | Measures market valuation and risk profile. |

---

## 2. Logic Layer

### 2.1 Schemas & Data Model
*   **Medallion Architecture**:
    *   **Bronze**: "Raw" fidelity. Schema is `Permissive` (schema evolution enabled) to capture all API variations without breaking.
    *   **Silver**: "Cleansed" fidelity. Enforced StructTypes. null checks, deduplication, and standardization (e.g., date formats).
    *   **Gold**: "Business" fidelity. Aggregated metrics (e.g., `Net Debt = Short + Long Term Debt - Cash`).
*   **Serving (Analytical Model)**:
    *   **Design Pattern**: **OBT (One Big Table)**.
    *   **Reasoning**: We denormalize Fundamental and Market data into a single wide table to enable sub-second dashboard queries without complex joins at read-time.

### 2.2 Storage Strategies
*   **Idempotency**: "Surgical Backfill".
    *   Instead of full table overwrites, we use `replaceWhere` on partition keys (e.g., `date='2025-01-01'`) to safely re-process specific days without affecting history.
*   **Lambda Architecture**:
    *   **Batch Path**: Handles high-accuracy, high-latency fundamental data logic.
    *   **Speed Path**: Handles low-latency, high-volume market data.
    *   **Merge**: The two paths converge in the Serving Layer.

---

## 3. Physical Layer

### 3.1 Storage Format
*   **Delta Lake**:
    *   **Format**: Parquet files + `_delta_log` (JSON transaction log).
    *   **Why**:
        *   **ACID Transactions**: Ensures partial writes (failed jobs) do not corrupt tables.
        *   **Time Travel**: Allows querying previous versions of data (`TIMESTAMP AS OF`).
        *   **Upsert Support**: Enables `MERGE` operations (simulated via `overwrite` in this specific env due to constraints).

### 3.2 Storage Locations
*   **S3 (AWS)**: The physical persistence layer.
    *   Path: `s3a://mzon-to-databricks-5482/`
    *   Structure: `/landing`, `/bronze`, `/silver`, `/gold`.
*   **Databricks Volumes**: A logical Unity Catalog wrapper.
    *   Path: `/Volumes/workspace/default/storage/...`
    *   **Purpose**: Decouples code from AWS Credentials. Allows SQL queries to access S3 data without injecting Access Keys.

### 3.3 Data Flow & Serving Strategy
The central nervous system of the engine is the **Hybrid Join** in `serving_layer.ipynb`.

1.  **Ingest**: APIs -> S3 Landing (JSON).
2.  **Process (Batch)**: Bronze -> Silver -> Gold (Financials).
3.  **Process (Speed)**: Bronze -> Silver -> Gold (Ticker Stream).
4.  **Merge (Serving Layer)**:
    *   **Technique**: **Forward-Fill Left Join**.
    *   **Logic**:
        ```sql
        SELECT * 
        FROM Speed_Layer (Stream) s
        LEFT JOIN Batch_Layer (Static) b 
        ON s.symbol = b.symbol 
        AND b.report_date = (SELECT MAX(date) FROM Batch WHERE symbol = s.symbol)
        ```
    *   **Result**: Every real-time price tick is enriched with the *latest available* financial context (e.g., "Apple's price right now is $150, based on Q3 Earnings").

This architecture ensures that the Dashboard always displays the most current market price while maintaining the context of the most recent financial fundamentals.

---

## 4. Schema Evolution & Data Dictionary

This section details how data attributes transform and evolve through the Medallion architecture (Bronze -> Silver -> Gold -> Serving).

### 4.1 Entity: Financial Fundamentals (Batch)
*   **Source**: FMP API (Income Statement, Balance Sheet, Cash Flow)
*   **Update Frequency**: Quarterly

| Attribute | Type | Bronze Layer (Raw) | Silver Layer (Cleansed) | Gold Layer (Business) | Serving Layer (Analytical) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **symbol** | String | `symbol` | `symbol` | `symbol` | `symbol` |
| **date** | Date | `date` | `date` | `date` | `report_date` |
| **revenue** | Money | `revenue` | `revenue` | `revenue` | *Used in calcs* |
| **costOfRevenue** | Money | `costOfRevenue` | `costOfRevenue` | *Used in calcs* | - |
| **grossProfit** | Money | `grossProfit` | `grossProfit` | `gross_margin` (Ratio) | - |
| **ebit** | Money | *Derived* | `ebit` | `ebit` | - |
| **incomeTaxExpense** | Money | `incomeTaxExpense` | `incomeTaxExpense` | `tax_expense` | `effective_tax_rate` (Ratio) |
| **netIncome** | Money | `netIncome` | `netIncome` | `nopat` (Derived) | - |
| **eps** | Money | `eps` | `eps` | - | - |
| **shares** | Count | `weightedAverageShsOutDil` | `weightedAverageShsOutDil` | `shares_outstanding` | *Used in Market Cap* |
| **cash** | Money | `cashAndCashEquivalents` | `cashAndCashEquivalents` | - | - |
| **receivables** | Money | `netReceivables` | `netReceivables` | *Used in WC* | - |
| **inventory** | Money | `inventory` | `inventory` | *Used in WC* | - |
| **payables** | Money | `accountPayables` | `accountPayables` | *Used in WC* | - |
| **workingCapital** | Money | *Derived* | *Derived* | `working_capital`, `delta_wc` | - |
| **totalAssets** | Money | `totalAssets` | `totalAssets` | - | - |
| **totalLiabilities** | Money | `totalLiabilities` | `totalLiabilities` | - | - |
| **totalDebt** | Money | `totalDebt` | `totalDebt` | `total_debt` | `total_debt` |
| **netDebt** | Money | `netDebt` | `netDebt` | `net_debt` | - |
| **depreciation** | Money | `depreciationAndAmortization`| `depreciationAndAmortization`| `depreciation` | - |
| **capex** | Money | `capitalExpenditure` | `capitalExpenditure` | `capex` | - |
| **freeCashFlow** | Money | `freeCashFlow` | `freeCashFlow` | `calculated_fcf` | `calculated_fcf` |
| **interestExpense** | Money | `interestExpense` | `interestExpense` | `interest_expense` | `cost_of_debt` (Ratio) |
| **liquidityRatio** | Ratio | *Derived* | *Derived* | `liquidity_ratio` | - |
| **interestCoverage**| Ratio | *Derived* | *Derived* | `interest_coverage_ratio` | - |

#### Evolution Logic
1.  **Bronze**: **Permissive**. JSON fields are ingested as string/structs.
2.  **Silver**: **Strict Cast**. Numeric fields cast to `Long` or `Decimal`.
3.  **Gold**: **Aggregated**.
    *   `nopat` = `ebit` - `incomeTaxExpense`
    *   `working_capital` = `netReceivables` - `accountPayables` (Simplified Proxy)
    *   `calculated_fcf` = `nopat` + `depreciation` - `delta_wc` - `capex`
4.  **Serving**: **Ratio-Based**.
    *   `effective_tax_rate` = `tax_expense` / (`nopat` + `tax_expense`)
    *   `cost_of_debt` = `interest_expense` / `total_debt`

### 4.2 Entity: Market Data (Stream)
*   **Source**: Finnhub API (Quote, Basic Financials)
*   **Update Frequency**: Real-time / Daily

| Attribute | Type | Bronze Layer (Raw) | Silver Layer (Cleansed) | Gold Layer (Business) | Serving Layer (Analytical) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **price** | Money | `c` | `close_price` | `close_price` | `close_price` |
| **beta** | Ratio | `beta` | `beta` | `beta` | `beta` |
| **volatility**| Ratio | *Derived* | *Derived* | `volatility` | `volatility` |
| **momentum** | Ratio | *Derived* | *Derived* | `momentum` | `momentum` |
| **marketCap** | Money | *Derived* | *Derived* | *Derived* | `market_cap` (`price` * `shares`) |
| **enterpriseValue**| Money | *Derived* | *Derived* | *Derived* | `enterprise_value` (`mkt_cap` + `net_debt`) |
| **wacc** | Ratio | *Derived* | *Derived* | *Derived* | `wacc` |
| **peRatio** | Ratio | *Derived* | *Derived* | *Derived* | `pe_ratio_implied` |

### 4.3 Entity: Serving Layer (Valuation Engine Output)
*   **Table Name**: `valuation_dashboard_v5`
*   **Nature**: One Big Table (OBT) - Hybrid Join of Stream & Batch.
*   **Update Frequency**: Real-time (triggered by speed layer).

| Column Name | Type | Origin | Description |
| :--- | :--- | :--- | :--- |
| **symbol** | String | Shared Key | Common identifier (e.g., "AAPL"). |
| **valuation_timestamp** | Timestamp | System | Exact time of the Hybrid Join. |
| **report_date** | Date | Batch Layer | Date of the fundamental report used (e.g., 2023-09-30). |
| **valuation_date** | Date | System | Date part of the valuation timestamp. |
| **close_price** | Double | Speed Layer | Most recent market price. |
| **beta** | Double | Speed Layer | Volatility relative to market. |
| **volatility** | Double | Speed Layer | Standard deviation of returns. |
| **momentum** | Double | Speed Layer | Rate of change in price. |
| **cost_of_equity** | Double | Calculated | `RiskFree + Beta * MarketRiskPremium`. |
| **calculated_fcf** | Long | Batch Layer | Free Cash Flow available to firm. |
| **cost_of_debt** | Double | Batch Layer | `Interest Expense / Total Debt` (Capped). |
| **effective_tax_rate** | Double | Batch Layer | `Tax Expense / Pre-Tax Income`. |
| **market_cap** | Double | Calculated | `Price * Shares Outstanding`. |
| **enterprise_value** | Double | Calculated | `Market Cap + Net Debt`. |
| **wacc** | Double | Calculated | Weighted Average Cost of Capital (The core valuation metric). |
| **pe_ratio_implied** | Double | Calculated | `Price / (NOPAT / Shares)`. |
