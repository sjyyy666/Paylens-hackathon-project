from pprint import pprint

from src import risk_engine
from src import contract_adapter

TEST_CASES = [
    {
        "name": "Low delay risk",
        "payment_delay_probability": 0.05,
        "contract_value": 30000,
        "cash_reserve": 50000,
        "monthly_cost": 10000,
        "upfront_pct": 0.20,
        "payment_terms_days": 30,
    },
    {
        "name": "Medium delay risk",
        "payment_delay_probability": 0.50,
        "contract_value": 30000,
        "cash_reserve": 50000,
        "monthly_cost": 10000,
        "upfront_pct": 0.20,
        "payment_terms_days": 30,
    },
    {
        "name": "High delay risk",
        "payment_delay_probability": 0.95,
        "contract_value": 30000,
        "cash_reserve": 50000,
        "monthly_cost": 10000,
        "upfront_pct": 0.20,
        "payment_terms_days": 30,
    },
    {
        "name": "Large contract",
        "payment_delay_probability": 0.50,
        "contract_value": 120000,
        "cash_reserve": 45000,
        "monthly_cost": 25000,
        "upfront_pct": 0.20,
        "payment_terms_days": 60,
    },
    {
        "name": "Strong upfront protection",
        "payment_delay_probability": 0.50,
        "contract_value": 120000,
        "cash_reserve": 45000,
        "monthly_cost": 25000,
        "upfront_pct": 0.70,
        "payment_terms_days": 30,
    },
]

def extract_result(result):
    return {
        "score": result.get("score"),
        "level": result.get("level"),
        "methodology_version": result.get("methodology_version"),
    }


for case in TEST_CASES:
    print("\n" + "=" * 60)
    print(case["name"])

    params = {
        "payment_probability": case["payment_delay_probability"],
        "contract_value": case["contract_value"],
        "cash_reserve": case["cash_reserve"],
        "monthly_cost": case["monthly_cost"],
        "upfront_pct": case["upfront_pct"],
        "payment_terms_days": case["payment_terms_days"],
    }

    print("\nOld engine:")
    old_result = risk_engine.analyse_contract(**params)
    pprint(extract_result(old_result))

    print("\nNew engine:")
    new_result = contract_adapter.analyse_contract(**params)
    pprint(extract_result(new_result))

    print("\nScore difference:")
    print(new_result["score"] - old_result["score"])