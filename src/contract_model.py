"""
Contract Model

This module provides the application-facing interface for the
rule-based Contract Risk Engine.

The ML Risk Engine should provide the customer's estimated probability
of paying on time. This module then combines that output with contract
and business cash-flow information.
"""

from __future__ import annotations

from typing import Any, Dict

try:
    # Works when imported as a package:
    # from src.contract_model import ContractModel
    from .contract_risk_engine import assess_contract_risk
except ImportError:
    # Works when running this file directly from inside src:
    from contract_risk_engine import assess_contract_risk


class ContractModel:
    """Application-facing wrapper for contract risk assessment."""

    def predict(
        self,
        payment_probability: float,
        contract_value: float,
        cash_reserve: float,
        monthly_cost: float,
        upfront_pct: float,
        delivery_time_days: int,
        payment_terms_days: int,
    ) -> Dict[str, Any]:
        """
        Assess the financial risk of a proposed contract.

        Args:
            payment_probability:
                Estimated probability that the customer pays on time.
                This should normally come from the ML Risk Engine and must
                be between 0 and 1.

            contract_value:
                Total value of the contract.

            cash_reserve:
                Currently available business cash.

            monthly_cost:
                Average monthly operating cost.

            upfront_pct:
                Upfront payment percentage as a decimal.
                Example: 0.25 means 25%.

            delivery_time_days:
                Number of days required to deliver the contract.

            payment_terms_days:
                Number of days the customer has to pay after delivery.

        Returns:
            A dictionary containing financial metrics, component scores,
            overall risk score, risk level, recommended upfront payment,
            and recommendations.
        """
        return assess_contract_risk(
            payment_probability=payment_probability,
            contract_value=contract_value,
            cash_reserve=cash_reserve,
            monthly_cost=monthly_cost,
            upfront_pct=upfront_pct,
            delivery_time_days=delivery_time_days,
            payment_terms_days=payment_terms_days,
        )

    def simulate(
        self,
        payment_probability: float,
        contract_value: float,
        cash_reserve: float,
        monthly_cost: float,
        upfront_pct: float,
        delivery_time_days: int,
        payment_terms_days: int,
    ) -> Dict[str, Any]:
        """
        Recalculate the contract risk after the user changes contract terms.

        This is useful for a before/after negotiation simulator.
        """
        return self.predict(
            payment_probability=payment_probability,
            contract_value=contract_value,
            cash_reserve=cash_reserve,
            monthly_cost=monthly_cost,
            upfront_pct=upfront_pct,
            delivery_time_days=delivery_time_days,
            payment_terms_days=payment_terms_days,
        )


if __name__ == "__main__":
    model = ContractModel()

    result = model.predict(
        payment_probability=0.72,
        contract_value=120000,
        cash_reserve=45000,
        monthly_cost=25000,
        upfront_pct=0.00,
        delivery_time_days=90,
        payment_terms_days=30,
    )

    print("Risk score:", result["risk_score"])
    print("Risk level:", result["risk_level"])
    print("Metrics:", result["metrics"])
    print("Recommended upfront:", result["recommended_upfront_pct"])
    print("Recommendations:")

    for recommendation in result["recommendations"]:
        print("-", recommendation)
