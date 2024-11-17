import polars as pl
import pathlib

root_path = pathlib.Path(__file__).parent

sellers = pl.scan_parquet(root_path.joinpath("olist_sellers_dataset.parquet"))
customers = pl.scan_parquet(root_path.joinpath("olist_customers_dataset.parquet"))
geolocation = pl.scan_parquet(root_path.joinpath("olist_geolocation_dataset.parquet"))
order_items = pl.scan_parquet(root_path.joinpath("olist_order_items_dataset.parquet"))
orders = pl.scan_parquet(root_path.joinpath("olist_orders_dataset.parquet"))
products = pl.scan_parquet(root_path.joinpath("olist_products_dataset.parquet"))
product_categories = pl.scan_parquet(
    root_path.joinpath("product_category_name_translation.parquet")
)

sales_data = (
    orders.join(order_items, on="order_id")
    .join(products, on="product_id")
    .join(sellers, on="seller_id")
    .join(customers, on="customer_id")
    .join(product_categories, on="product_category_name")
    .select(
        [
            "product_id",
            "product_category_name_english",
            "seller_id",
            "seller_state",
            "order_status",
            "order_purchase_timestamp",
            "order_id",
            "customer_id",
            "customer_state",
            "price",
            "freight_value",
        ]
    )
    .with_columns(
        pl.col("order_purchase_timestamp").str.to_datetime(),
        pl.lit(1.0).alias("quantity"),
    )
    .with_columns(
        pl.col("order_purchase_timestamp").dt.year().alias("year"),
        pl.col("order_purchase_timestamp").dt.month().alias("month"),
        pl.col("order_purchase_timestamp").dt.quarter().alias("quarter"),
        pl.col("order_purchase_timestamp").dt.week().alias("week"),
    )
    .with_columns(
        (pl.col("price") * pl.col("quantity") + pl.col("freight_value")).alias(
            "revenue"
        )
    )
    .filter(pl.col("order_status") == "delivered")
    .filter(pl.col("year") > 2016)
    .drop(["order_purchase_timestamp", "order_status"])
    .collect()
)
