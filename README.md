# PayLens

> **Know whether your business can afford the deal before you sign it.**
>
> *Winning the contract shouldn't mean financing your customer.*

PayLens is a pre-contract cash-flow stress-testing tool for Australian SMEs supplying larger organisations. It combines customer payment behaviour, the economics of the proposed contract, and the supplier's financial position to assess deal resilience and identify payment terms that could make the contract more sustainable.

The application combines:

- Customer payment-delay analysis
- Contract and cash-flow exposure analysis
- Transparent risk scoring
- Plain-English recommendations
- A negotiation simulator for testing revised payment terms

PayLens is designed to support better commercial decisions **before a contract is signed**. It does not replace professional financial, legal, or credit advice.

---

## My Contributions

My main contributions to the PayLens project included:

### 1. Data Processing

- Processed and cleaned the raw company-payment data.
- Handled data preparation and transformation to produce reliable, structured datasets.
- Converted the cleaned data into training data suitable for the machine-learning payment-delay model.

### 2. Contract Risk Engine

- Developed the rule-based Contract Risk Engine.
- Implemented calculations for contract exposure, cash-flow pressure, payment timing, upfront payment protection, and customer payment-delay risk.
- Designed the risk-scoring logic to provide transparent and interpretable contract-risk assessments.
- Supported risk recommendations and comparisons between different contract payment terms.

---

## Try It

Two hosted deployments. Start with whichever suits you:

| | | |
|---|---|---|
| **Live demo** | https://windsorrr09-sys.github.io/ai-hackathon-2026/ | No sign-in |
| **Full application** | https://ai-hackathon-2026-hzmxizxcs54vqy4xkgydpa.streamlit.app | Streamlit sign-in required |
| **Source** | https://github.com/windsorrr09-sys/ai-hackathon-2026 | |

**Live demo** — no sign-in, no install, no Python; runs entirely in your browser.
It uses the demo dataset and a mock delay model. It is deployed from this
repository by [GitHub Actions](.github/workflows/pages.yml) on every push to
`main`, rebuilt from `web/src` and checked against the committed build, so the
page you see can never drift from the source you can read.

**Full application** — the Streamlit app running the trained logistic-regression
model against the full Payment Times company history (54,420 company-periods,
real ABNs). Streamlit Community Cloud requires viewers to sign in with a free
account; the app is not broken if you meet a sign-in page.

Both score through the same contract engine, so exposure scores match. The About
panel in either one names the data source and the model actually in use, so you
can confirm which you are looking at.

To run the demo build locally instead, open `web/index.html` in a browser, or
rebuild it from source:

```bash
python tools/build_web.py
```

For the full application with real data, see [Running the Application](#running-the-application).

---

## Table of Contents

- [Try It](#try-it)
- [Overview](#overview)
- [Key Features](#key-features)
- [How PayLens Works](#how-paylens-works)
- [Application Flow](#application-flow)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Running the Application](#running-the-application)
- [Configuration and Data Sources](#configuration-and-data-sources)
- [Risk Analysis](#risk-analysis)
- [Contract Analysis](#contract-analysis)
- [Negotiation Simulator](#negotiation-simulator)
- [Model and Product Boundaries](#model-and-product-boundaries)
- [Current Implementation Status](#current-implementation-status)
- [Testing and Validation](#testing-and-validation)
- [Known Limitations](#known-limitations)
- [Future Improvements](#future-improvements)
- [Team Development Notes](#team-development-notes)
- [Disclaimer](#disclaimer)

---

## Overview

Late customer payments can create serious cash-flow pressure for small businesses. A contract may appear profitable but still be difficult to deliver if the business must pay staff, suppliers, and operating expenses before receiving payment from the customer.

PayLens helps users answer questions such as:

- Is this customer likely to pay late?
- How much cash will the business need to finance the contract?
- How long might the business need to wait before receiving payment?
- Could the waiting period exceed the business's available cash runway?
- Would a larger upfront payment reduce the financial risk?
- Would shorter payment terms or milestone-based payments make the contract safer?

The application presents these results through an interactive Streamlit interface.

---

## Key Features

### 1. Customer Search

Users can search for a company by:

- Company name
- Australian Business Number (ABN)

The application also provides suggested companies for quick demonstration and testing.

### 2. Customer Payment-Risk Analysis

After selecting a company, PayLens retrieves the company's available features and estimates its payment-delay risk.

The application can display:

- Customer information
- Historical payment information
- Estimated payment-delay probability
- Model information
- Supporting customer-level indicators

The payment-delay model is intended to estimate the probability of **high payment delay**, rather than general business failure or profitability.

### 3. Contract Exposure Analysis

Users can enter proposed contract details, including:

- Contract value
- Available cash reserve
- Monthly operating costs
- Upfront payment percentage
- Payment terms

The application then estimates the financial pressure created by the contract.

### 4. Transparent Risk Scoring

PayLens uses interpretable calculations rather than presenting only an unexplained prediction.

The contract analysis considers factors such as:

- Net contract exposure
- Contract exposure relative to available cash
- Waiting period before payment
- Cash runway
- Estimated operating costs during the waiting period
- Upfront payment protection
- Customer payment-delay risk

### 5. Plain-English Recommendations

The application converts the calculated results into practical next steps, such as:

- Requesting a larger upfront payment
- Reducing the amount of cash that must be financed
- Using milestone-based invoicing
- Shortening payment terms
- Using staged delivery
- Reviewing customer payment protections

### 6. Negotiation Simulator

After analysing a deal, users can test alternative contract structures.

The simulator allows users to change:

- Upfront payment
- Payment terms

The customer, contract value, and cash position remain unchanged while the revised deal is recalculated.

Users can compare:

- The current contract
- The revised contract
- Changes in risk and financial exposure
- Suggested negotiation structures

### 7. User-Friendly Interface

The application includes:

- A responsive wide-page layout
- Search and selection controls
- Interactive input fields
- Quick-pick companies
- Risk and exposure cards
- A revised-terms simulator
- Compatibility helpers for Streamlit UI behavior
- A final error guard to avoid exposing technical stack traces to users

---

## How PayLens Works

The application follows this general pipeline:

```text
User searches for a company
            |
            v
Company is selected
            |
            v
Customer features and history are loaded
            |
            v
Payment-delay risk is estimated
            |
            v
User enters contract details
            |
            v
Contract exposure is calculated
            |
            v
Risk score and recommendations are displayed
            |
            v
User tests revised payment terms
            |
            v
Current and revised deals are compared
```

The main application entry point is `app.py`.

The application delegates data and model access to `src.services`, while separate modules handle state management, risk calculations, recommendations, formatting, and UI components.

---

## Application Flow

### Step 1: Search for a Customer

The user enters a company name or ABN into the search field and selects **Analyse Customer**.

PayLens calls:

```python
services.search_company(query)
```

If the search returns an exact match or only one result, the company can be selected automatically.

### Step 2: Review Customer Information

Once a company is selected, PayLens retrieves:

```python
services.get_company_features(company_id)
services.get_company_history(company_id)
services.predict_payment_risk(features)
```

The customer section displays the available company information, history, and payment-risk result.

### Step 3: Enter Contract Details

The user enters:

- Contract value
- Available cash
- Monthly operating costs
- Payment terms
- Upfront payment

The input values are normalised and validated through the state-management and formatting modules.

### Step 4: Analyse the Deal

The user selects **Analyse My Deal**.

PayLens combines the customer risk result with the contract inputs and calls:

```python
services.analyse_contract(...)
```

The result is shown as a contract exposure card.

### Step 5: Simulate Revised Terms

The user can modify:

- Upfront payment
- Payment terms

PayLens recalculates the revised contract and compares it with the current deal.

The application can also suggest a revised contract structure.

---

## Technology Stack

- **Python** — application and analysis logic
- **Streamlit** — interactive web application framework
- **HTML/CSS** — interface styling and presentation
- **Pandas / data-processing tools** — used by the data and modelling pipeline where applicable
- **Rule-based risk calculations** — interpretable contract exposure analysis
- **Machine learning payment-delay model** — customer payment-delay estimation
- **Git/GitHub** — source-code management and collaboration

---

## Project Structure

The current application is organised around the following modules:

```text
.
├── app.py
├── assets/
│   └── favicon.png
├── src/
│   ├── services.py
│   ├── mock_services.py
│   ├── risk_engine.py
│   ├── contract_risk_engine.py
│   ├── contract_model.py
│   ├── recommendations.py
│   ├── state.py
│   ├── formatting.py
│   └── ui/
│       ├── compat.py
│       ├── components.py
│       └── styles.py
├── preprocess/
│   ├── clean.xlsx
│   ├── build_training_data.py
│   ├── training_data.csv
│   ├── training_data.xlsx
│   ├── company_history.csv
│   └── company_history.xlsx
└── README.md
```

> The exact contents of the repository may change as the project develops. The structure above describes the intended separation of responsibilities.

### `app.py`

The main Streamlit application.

Responsibilities include:

- Page configuration
- Navigation
- Search controls
- Customer selection
- Contract input fields
- Contract analysis
- Negotiation simulator
- Rendering UI sections
- Connecting the UI to service and analysis modules

### `src/services.py`

The main data and model entry point.

The application calls this module rather than directly accessing individual data or model implementations.

This creates a service boundary that makes it easier to replace mock services with production data and model services later.

### `src/mock_services.py`

Provides demonstration data and mock payment-delay predictions.

This is useful for:

- Local development
- UI testing
- Hackathon demonstrations
- Testing the user journey without a live backend

### `src/risk_engine.py`

Provides deterministic contract exposure and risk calculations used by the application flow.

This module is intended to make contract-related financial risk transparent and explainable.

### `src/contract_risk_engine.py`

Provides the separate rule-based Contract Risk Engine.

It evaluates whether the business can financially support a proposed contract based on contract value, cash reserve, operating costs, payment timing, upfront payment, and customer payment-delay probability.

### `src/contract_model.py`

Provides an application-facing wrapper around the Contract Risk Engine.

It exposes methods such as:

```python
predict(...)
simulate(...)
```

The wrapper is intended to provide a stable interface for the rest of the application.

### `src/recommendations.py`

Converts analysis results into plain-English actions and suggestions.

### `src/state.py`

Manages the user's journey and Streamlit session state.

It handles tasks such as:

- Initialising default values
- Selecting a company
- Clearing searches
- Reading contract inputs
- Detecting changed inputs
- Resetting the simulator
- Applying suggested terms

### `src/formatting.py`

Provides formatting and parsing helpers, including:

- Currency formatting
- Amount parsing
- Input normalisation

### `src/ui/`

Contains reusable UI functionality.

Typical responsibilities include:

- HTML components
- CSS styling
- Streamlit compatibility helpers
- Cards, panels, result blocks, and simulator components

---

## Getting Started

### Prerequisites

Install the following before running the application:

- Python 3.10 or later
- `pip`
- Git
- A virtual environment tool such as `venv`

### Clone the Repository

```bash
git clone <your-repository-url>
cd <your-repository-folder>
```

Replace the placeholder repository URL and folder name with the actual project details.

### Create a Virtual Environment

On Windows PowerShell:

```powershell
python -m venv .venv
```

Activate the environment:

```powershell
.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Install Dependencies

If the repository contains a `requirements.txt` file:

```bash
pip install -r requirements.txt
```

If the dependency file has not yet been created, install the main application dependency:

```bash
pip install streamlit
```

Additional dependencies may be required by the preprocessing and machine-learning modules.

---

## Running the Application

From the project root directory, run:

```bash
streamlit run app.py
```

Streamlit will provide a local URL, usually similar to:

```text
http://localhost:8501
```

Open the URL in a browser.

### Important

Run the command from the directory containing `app.py`, not from inside `src/`.

Correct:

```text
project-root/
└── app.py
```

Then:

```bash
streamlit run app.py
```

---

## Configuration and Data Sources

PayLens supports a service-based architecture.

The application currently supports a mock-data mode for demonstration and development. The service layer is designed to make it possible to replace mock data with real data and production model services.

The main service boundary is:

```python
from src import services
```

The application expects service functions for:

```python
services.search_company(...)
services.suggested_companies(...)
services.get_company_features(...)
services.get_company_history(...)
services.predict_payment_risk(...)
services.analyse_contract(...)
```

The exact backend behavior depends on the current implementation of `src.services`.

### Preprocessing Outputs

The data-processing workflow produces four main output files:

```text
preprocess/training_data.csv
preprocess/training_data.xlsx
preprocess/company_history.csv
preprocess/company_history.xlsx
```

The two training-data files are intended for supervised machine-learning development.

The two company-history files preserve historical company-level information for analysis and display.

---

## Risk Analysis

PayLens separates customer payment behavior from business contract exposure.

### Customer Payment-Delay Risk

The machine-learning component is intended to estimate:

```text
P(high_payment_delay = 1)
```

In other words, the probability that the customer will experience high payment delay.

This is not the same as:

- Probability of paying on time
- Probability of bankruptcy
- Probability of insolvency
- Probability of default in every financial sense
- Company profitability
- Available cash reserves
- Contract profitability

The probability must therefore be interpreted consistently throughout the application.

### Contract Risk

The contract component evaluates the financial pressure created by a proposed deal.

Relevant factors include:

- Contract value
- Upfront payment
- Remaining amount to be financed
- Available cash
- Monthly operating costs
- Delivery period
- Payment terms
- Expected waiting period
- Customer payment-delay probability

### Risk Score

The overall risk score combines multiple components.

The exact weights and thresholds are defined in the relevant risk-engine configuration.

The score is intended to be:

- Transparent
- Interpretable
- Consistent
- Useful for comparing alternative contract structures

It should not be interpreted as a guaranteed prediction of future financial loss.

---

## Contract Analysis

The Contract Risk Engine uses the following conceptual calculations.

### Net Exposure

```text
net exposure = contract value × (1 − upfront percentage)
```

This estimates the amount of contract value the business must finance after the upfront payment.

### Total Waiting Period

```text
total waiting days = delivery time + payment terms
```

This represents the estimated time between starting delivery and receiving the remaining payment.

### Contract-to-Cash Ratio

```text
contract-to-cash ratio = net exposure / available cash reserve
```

A higher ratio indicates that the contract requires more financing relative to the business's available cash.

### Cash Runway

```text
cash runway in months = available cash / monthly operating costs
```

This estimates how many months the business can cover operating costs using its current cash reserve, assuming the simplified model assumptions hold.

### Estimated Cost During Waiting Period

```text
estimated waiting cost =
    monthly operating costs / 30 × total waiting days
```

This is a simplified estimate of operating costs incurred before payment arrives.

### Recommended Upfront Payment

The engine can estimate an upfront payment percentage intended to keep net exposure within a target multiple of available cash.

This recommendation is a modelling output, not a legal or commercial requirement.

---

## Negotiation Simulator

The simulator is designed to help users explore how contract changes may affect risk.

The user can modify:

- Upfront payment
- Payment terms

The simulator keeps the following unchanged:

- Selected customer
- Contract value
- Available cash
- Monthly operating costs

It then recalculates the revised contract and displays a comparison with the current deal.

Typical negotiation strategies suggested by the application may include:

- Increasing upfront payment
- Shortening payment terms
- Introducing milestone payments
- Using staged delivery
- Reducing the amount of cash advanced by the business

---

## Model and Product Boundaries

PayLens is a decision-support prototype.

It does not currently claim to:

- Guarantee that a customer will pay
- Predict bankruptcy or insolvency
- Determine whether a contract is legally enforceable
- Assess every aspect of customer creditworthiness
- Calculate complete accounting profit
- Replace professional financial advice
- Replace legal review
- Automatically approve or reject contracts

The application should be used to identify potential risk factors and support further investigation.

---

## Current Implementation Status

### Implemented or represented in the current application

- Streamlit application shell
- Company search flow
- Suggested companies
- Customer selection
- Customer feature and history loading
- Payment-delay risk display
- Contract input form
- Contract analysis action
- Exposure result display
- Revised-term simulator
- Recommendation display
- Session-state management
- UI compatibility helpers
- Error handling at the page level
- Mock service support for demonstrations

### Integration point requiring confirmation

The current `app.py` application flow calls:

```python
services.analyse_contract(...)
```

and imports the application risk functions through:

```python
from src.risk_engine import ...
```

`src.contract_adapter` bridges the two: it calls `contract_risk_engine.assess_contract_risk` and falls back to `risk_engine.analyse_contract` only if that raises, so the deal panel always renders.

The project consistently uses:

```python
payment_delay_probability
```

for the machine-learning output representing:

```text
P(high_payment_delay = 1)
```

The application should not interpret this value as an on-time payment probability.

Verified:

1. **Which risk engine is called by `src.services`** — `contract_risk_engine.py`, via `src/contract_adapter.py`, with `risk_engine.analyse_contract` as the fallback.
2. **Whether `contract_model.py` is used by the application** — no; it is a thin wrapper over the same contract engine, kept as a documented reference interface.
3. **Whether the parameter name and probability meaning are consistent** — yes. The value is the delay probability at every layer and is never inverted. `contract_adapter.analyse_contract` keeps the historical parameter name `payment_probability` but documents and passes it through as the delay probability.
4. **Whether displayed customer risk rises with delay probability** — yes, asserted in `tests/test_contract_adapter.py` and `tests/test_contract_risk_engine.py`.
5. Whether the simulator recalculates the same engine used for the main deal analysis.

---

## Testing and Validation

At minimum, test the following workflows.

### Application Startup

```bash
streamlit run app.py
```

Confirm that:

- The page loads successfully.
- No stack trace is shown to the user.
- The navigation and search interface render correctly.

### Company Search

Test:

- Exact company-name search
- Partial company-name search
- ABN search
- Empty search
- Search with no results
- Selecting a suggested company

### Contract Input Validation

Test:

- Valid currency values
- Comma-separated values such as `120,000`
- Values using shorthand such as `120k`, if supported
- Empty values
- Invalid amounts
- Zero cash reserve
- Zero monthly operating costs
- Zero upfront payment
- Full upfront payment
- Long payment terms

### Risk Direction

Test at least:

```text
payment-delay probability = 0.0
payment-delay probability = 0.5
payment-delay probability = 1.0
```

The customer-risk component should increase as the delay probability increases.

### Contract Comparison

Test:

- No upfront payment versus a larger upfront payment
- Long payment terms versus short payment terms
- Low cash reserve versus high cash reserve
- Short delivery versus long delivery
- Current deal versus revised deal

### Error Handling

Confirm that:

- Missing customer data is handled gracefully.
- Missing payment-risk output falls back to the intended neutral assumption.
- Invalid contract inputs cannot trigger an invalid analysis.
- Technical exceptions are logged without exposing a full stack trace to the user.

---

## Known Limitations

- The current application includes mock-data support.
- The production data and model service integration may still be under development.
- The contract calculations are simplified and should not be treated as a complete financial model.
- Waiting-period costs are estimated using a simplified daily operating-cost calculation.
- The model does not capture every possible cash inflow or outflow.
- The payment-delay prediction depends on the quality and coverage of the training data.
- Historical company records may be incomplete.
- A predicted payment-delay probability is not a guarantee of actual customer behavior.
- The UI-level error guard can hide the underlying error from the user; developers should inspect application logs during debugging.
- The exact integration between the separate Contract Risk Engine and the current service layer should be confirmed before deployment.

---

## Future Improvements

Potential next steps include:

### Data and Model

- Connect the application to the final production data source.
- Replace mock services with live services.
- Add model versioning.
- Add model performance metrics.
- Add calibration for predicted probabilities.
- Monitor data drift and model drift.
- Improve handling of missing and revised company records.

### Contract Engine

- Integrate `ContractModel` directly into `src.services`.
- Support milestone-payment structures.
- Include supplier payment schedules.
- Include payroll and tax obligations.
- Model multiple payment events.
- Add scenario analysis for delayed, partial, or disputed payments.
- Add sensitivity analysis for cash reserve and monthly costs.

### User Experience

- Add downloadable reports.
- Add a contract-summary export.
- Add explanations for each score component.
- Add clearer uncertainty indicators.
- Improve accessibility.
- Add more detailed comparison charts.
- Add multilingual support.

### Engineering

- Add automated unit tests.
- Add integration tests for the Streamlit workflow.
- Add continuous integration through GitHub Actions.
- Add a `requirements.txt` or `pyproject.toml`.
- Add environment-variable configuration.
- Add structured logging.
- Add a deployment configuration.

---

## Team Development Notes

### Running Locally

Use a virtual environment and start the application from the project root:

```powershell
.venv\Scripts\Activate.ps1
streamlit run app.py
```

### Code Ownership Boundaries

The project separates responsibilities across modules:

- UI and page flow: `app.py` and `src/ui/`
- Session state: `src/state.py`
- Data and model access: `src/services.py`
- Demonstration backend: `src/mock_services.py`
- Customer payment-delay model: model-service layer
- Contract exposure calculations: risk-engine modules
- Recommendations: `src/recommendations.py`
- Data preparation: `preprocess/`

When changing a function signature or risk-probability meaning, update every caller and every relevant documentation string.

### Probability Naming Convention

Use:

```python
payment_delay_probability
```

for the ML output representing:

```text
P(high_payment_delay = 1)
```

Do not use `payment_probability` if the value actually represents payment delay.

This naming convention helps prevent a dangerous inversion where high delay probability is accidentally treated as high on-time payment probability.

---

## Disclaimer

PayLens is a hackathon prototype intended for educational, exploratory, and decision-support purposes.

Its outputs are estimates based on simplified assumptions, available data, and model behavior. Users should independently verify important financial, commercial, and legal decisions with qualified professionals.

**Do not rely on PayLens as the sole basis for signing, rejecting, or restructuring a contract.**
