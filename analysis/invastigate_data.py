
from pathlib import Path
import pandas as pd

DATASET_DIR = (
    Path.home()
    / "hackaton"
    / "dataset-hacktahton-road2tech"
)

# 1. Investigar ventas negativas y faltantes
sales = pd.read_csv(DATASET_DIR / "sales_daily.csv")

print("\n=== VENTAS NEGATIVAS ===")
print(
    sales.loc[
        (sales["units_sold"] < 0)
        | (sales["net_sales"] < 0),
        ["date", "store_id", "sku", "units_sold",
         "unit_price", "gross_sales", "discount_amount",
         "net_sales", "promo_id"]
    ].head(10).to_string(index=False)
)

print("\n=== VENTAS SIN units_sold ===")
print(
    sales.loc[sales["units_sold"].isna()].head(10)
    .to_string(index=False)
)

print("\n=== DUPLICADOS EXACTOS DE VENTAS ===")
print(
    sales.loc[sales.duplicated(keep=False)]
    .head(10)
    .to_string(index=False)
)

# 2. Investigar inventario
inventory = pd.read_csv(
    DATASET_DIR / "inventory_daily.csv"
)

print("\n=== INVENTARIO NEGATIVO ===")
print(
    inventory.loc[
        inventory["closing_qty"] < 0
    ].head(10).to_string(index=False)
)

print("\n=== STOCKOUT MAYOR A 24 HORAS ===")
print(
    inventory.loc[
        inventory["stockout_hours"] > 24
    ].head(10).to_string(index=False)
)

# Comprobar la ecuación de inventario
expected_closing = (
    inventory["opening_qty"]
    + inventory["received_qty"]
    - inventory["units_sold"]
    - inventory["expired_qty"]
    - inventory["damaged_qty"]
)

inventory["difference"] = (
    inventory["closing_qty"] - expected_closing
)

print("\n=== DIFERENCIAS EN LA ECUACIÓN ===")
print("Registros con diferencia:", (
    inventory["difference"].abs() > 0.001
).sum())

print(
    inventory.loc[
        inventory["difference"].abs() > 0.001,
        ["date", "store_id", "sku", "opening_qty",
         "received_qty", "units_sold", "expired_qty",
         "damaged_qty", "closing_qty", "difference"]
    ].head(10).to_string(index=False)
)
