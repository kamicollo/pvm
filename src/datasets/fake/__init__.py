"""Fake datasets for testing and demonstration purposes."""

from typing import TypedDict

import faker
import numpy as np
import polars as pl


class SalesRecord(TypedDict):
    """Sales record."""

    year: int
    country: str
    currency: str
    sku: str
    customer: str
    unit_price: float
    fx_rate: float
    volume: float
    flat_fee: float
    unit_cost: float
    cost_fx_rate: float


def generate_sales() -> pl.DataFrame:
    """
    Generate a fake sales dataset.

    Returns:
        pl.DataFrame: Sales dataset.

    """
    fake = faker.Faker()
    fake.seed_instance(42)
    fake.country()
    rng = np.random.default_rng(42)

    num_countries = 4
    num_products = 5
    num_customers = 10
    country_currencies = [(fake.country(), fake.currency_code()) for _ in range(num_countries)]
    fx_rates = {currency: rng.uniform(0.5, 1.5) for _, currency in country_currencies}

    skus = ["SKU" + str(i) for i in range(num_products)]
    base_prices = {sku: rng.uniform(5, 100) for sku in skus}
    base_margins = {sku: rng.uniform(0.6, 0.8) for sku in skus}

    customers = [fake.company() for _ in range(num_customers)]
    years = [2020, 2021, 2022, 2023]

    data = []

    for year in years:
        fx_rates = {currency: rng.normal(rate, 0.05) for currency, rate in fx_rates.items()}
        for country, currency in country_currencies:
            for sku in skus:
                for customer in customers:
                    record: SalesRecord = {
                        "year": year,
                        "country": country,
                        "currency": currency,
                        "sku": sku,
                        "customer": customer,
                        "unit_price": rng.normal(base_prices[sku], 5),
                        "fx_rate": fx_rates[currency],
                        "volume": rng.gamma(25, 3),
                        "flat_fee": rng.uniform(-20, 20) if rng.binomial(n=1, p=0.2) else 0,
                        "cost_fx_rate": 0,
                        "unit_cost": 0,
                    }
                    record["unit_cost"] = rng.normal(record["unit_price"] * base_margins[sku], 2)
                    record["cost_fx_rate"] = record["fx_rate"] * rng.normal(1, 0.05)
                    if rng.binomial(n=1, p=0.5):
                        data.append(record)

    return pl.DataFrame(data).with_columns(
        (pl.col("unit_price") * pl.col("fx_rate")).alias("price_in_lc"),
        (pl.col("unit_cost") * pl.col("cost_fx_rate")).alias("cost_in_lc"),
        (pl.col("unit_price") * pl.col("volume") + pl.col("flat_fee")).alias("revenue"),
        (pl.col("unit_cost") * pl.col("volume")).alias("cost"),
    )
