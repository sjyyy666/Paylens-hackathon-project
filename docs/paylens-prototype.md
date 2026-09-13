PayLens

Know the payment risk before you sign the deal.

PayLens helps a small business decide whether it can afford to take on a
large B2B customer.

The product separates two questions:

Customer payment-delay risk: How likely is the customer to pay late?

Contract risk: Given this customer's payment risk, can the business
financially support the proposed contract?

Customer risk ≠ Contract risk. The same customer can be a small risk for
one business and a serious risk for another.

The customer payment-delay model and customer data may be mocked in the
frontend prototype. The Contract Model is deterministic and rule-based.

Run it

Install the dependencies:

pip install -r requirements.txt

Run the Streamlit application:

streamlit run app.py

For a local run, open:

http://localhost:8502

Python 3.9+ and Streamlit 1.41 or newer are supported.

The deployed demo URLs, if available, should be treated as deployment
configuration rather than as part of the core application logic.

Standalone website

web/index.html is a single-file version of the product.

It can be opened directly in a browser without installing Python or
Streamlit.

The browser scoring implementation is intended to mirror the Python
Contract Model. Rebuild the web version after changing the relevant
frontend source files:

python tools/build_web.py

Demo path

A typical demonstration follows this sequence:

Select or search for a demo customer.

Review the customer's historical payment profile.

Review the ML payment-delay risk.

Enter the proposed contract details.

Click Analyse My Deal.

Review the separate contract-risk score.

Change the upfront payment or payment terms.

Recalculate the contract risk and compare the result.

The important product message is:

Same customer. Different deal structure. Lower or higher contract exposure.

Project structure

app.py                         Streamlit page composition and callbacks

src/services.py                Only data/model entry point used by the UI
src/mock_services.py           Demo companies and mock payment-risk model
src/real_services.py           Real-data service implementation
src/model_service.py           ML model loading and prediction adapter
src/ml_process.py              ML data preparation, training, and evaluation

src/contract_model.py           Application-facing Contract Model wrapper
src/contract_risk_engine.py     Deterministic contract-risk calculations

src/recommendations.py          Plain-English next steps
src/state.py                    Journey state machine
src/formatting.py               Currency parsing and display helpers

src/ui/components.py            Pure HTML builders
src/ui/styles.py                Stylesheet
src/ui/compat.py                Streamlit compatibility helpers

tests/                          Unit tests and full journey tests
tools/preview.py                Static previews and screenshots

Risk-model separation

ML Risk Engine

The ML Risk Engine predicts customer payment-delay risk from historical
payment behaviour.

Its current model is binary Logistic Regression using the locked feature
schema documented in PayLens ML Data Contract.

Its output includes a payment-delay probability and explanatory factors.

Contract Model

The Contract Model does not train an ML model.

It receives:

payment_delay_probability

where the value means the estimated probability that the customer pays late,
matching the ML output P(high_payment_delay = 1). The adapter parameter in
src/contract_adapter.py is still spelled payment_probability, but it carries
the delay probability and is documented as such.

It also receives:

contract_value
cash_reserve
monthly_cost
upfront_pct
delivery_time_days
payment_terms_days

It returns:

{
    "risk_score": 0.0,
    "risk_level": "LOW",
    "metrics": {},
    "component_scores": {},
    "recommended_upfront_pct": 0.0,
    "recommendations": [],
}

The ML layer produces payment-delay probability and the contract layer
consumes it directly. Do not invert it with
payment_probability = 1 - payment_delay_probability: that would make the
worst-paying customers score as the safest.

The two scores must be displayed separately in the UI.

Plugging in real data and ML

The UI should continue to call only src/services.py.

To use real data:

Implement or update src/real_services.py with the same public
functions and return shapes.

Load the trained ML artifact through src/model_service.py.

Return the existing UI-compatible payment-risk output.

Pass the converted payment probability into src/contract_model.py.

Keep the mock backend available as a fallback.

Expected service functions include:

def search_company(query: str) -> list:
    # [
    #   {
    #       "company_id": "...",
    #       "name": "...",
    #       "abn": "...",
    #       "industry": "...",
    #       "size_band": "...",
    #       "is_demo": False,
    #   }
    # ]

def get_company_features(company_id: str) -> dict:
    # Historical payment-behaviour features

def get_company_history(company_id: str):
    # Historical reporting-period data

def predict_payment_risk(features: dict) -> dict:
    # {
    #   "probability": 0.0,
    #   "level": "LOW",
    #   "factors": [],
    #   "confidence": "standard",
    #   "model": "logistic-v1",
    # }

The service facade should handle backend errors gracefully and preserve
the UI output shape.

Contract Model interface

The current Contract Model exposes:

from src.contract_model import ContractModel

model = ContractModel()

result = model.predict(
    payment_probability=0.80,
    contract_value=120000,
    cash_reserve=45000,
    monthly_cost=25000,
    upfront_pct=0.00,
    delivery_time_days=90,
    payment_terms_days=30,
)

The result contains:

result["risk_score"]
result["risk_level"]
result["metrics"]
result["component_scores"]
result["recommended_upfront_pct"]
result["recommendations"]

The model also supports recalculation through:

model.simulate(...)

This is intended for the frontend's contract-negotiation interaction.

Contract exposure methodology

The Contract Model is a transparent prototype heuristic. It is not a
validated commercial credit score.

The current implementation considers:

Customer payment risk

Net contract exposure relative to available cash

Time until payment relative to cash runway

Upfront-payment protection

The principal inputs are:

net_exposure = contract_value * (1 - upfront_pct)

total_waiting_days = delivery_time_days + payment_terms_days

The model also calculates:

Contract-to-cash ratio

Cash runway in months

Estimated operating cost during the waiting period

Waiting-cost-to-cash ratio

Recommended upfront payment percentage

Risk bands are:

0–30   LOW
31–55  MODERATE
56–75  HIGH
76–100 CRITICAL

The exact formulas and thresholds are implemented in
src/contract_risk_engine.py.

Tests

Run the existing test suite:

python -m pytest

Alternatively:

python -m unittest discover -s tests -t .

For a direct Contract Model smoke test:

python -m src.contract_model

The smoke test should print:

Risk score

Risk level

Financial metrics

Recommended upfront payment

Recommendations

The project should also test:

Risk-score bounds

Risk-band boundaries

Zero cash

Zero operating costs

Zero contract value

100% upfront payment

Long payment terms

Large and small contracts

Monotonicity when upfront payment increases

Monotonicity when payment terms decrease

Mock and real service adapters

ML-to-Contract-Model probability conversion

Frontend journey and reset flow

Limitations

PayLens is a decision-support prototype.

The ML results are based on the available historical reporting data and
should not be presented as a validated credit score.

The Contract Model is a transparent heuristic and should not be treated as
a legal, financial, lending, or credit decision.

The prepared dataset, target definition, feature mapping, and temporal
evaluation must be reviewed before production use.