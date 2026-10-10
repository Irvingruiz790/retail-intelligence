
from pathlib import Path
import math
import re

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


# --------------------------------------------------
# Configuracion y rutas
# --------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT.parent / "dataset-hacktahton-road2tech"

app = FastAPI(
    title="Retail Intelligence API",
    description="Dashboard, demanda e inventario para tiendas retail",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Solo para el prototipo del hackathon
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def normalize_sku(value):
    """Unifica, por ejemplo, SKU-100101 y SKU100101."""
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def load_csv(filename, dates=None):
    path = DATA_DIR / filename

    if not path.exists():
        raise FileNotFoundError(f"No se encontro el archivo: {path}")

    return pd.read_csv(path, parse_dates=dates or [])


# --------------------------------------------------
# Cargar datos una sola vez al iniciar la API
# --------------------------------------------------

sales = load_csv(
    "sales_model_baseline.csv",
    dates=["date"],
)

inventory = load_csv(
    "inventory_daily.csv",
    dates=["date"],
)

products = load_csv("products.csv")
stores = load_csv("stores.csv")

sales["sku_key"] = sales["sku"].map(normalize_sku)
inventory["sku_key"] = inventory["sku"].map(normalize_sku)
products["sku_key"] = products["sku"].map(normalize_sku)

sales["units_sold"] = pd.to_numeric(
    sales["units_sold"], errors="coerce"
).fillna(0)

sales["net_sales"] = pd.to_numeric(
    sales["net_sales"], errors="coerce"
).fillna(0)

for column in [
    "opening_qty",
    "received_qty",
    "units_sold",
    "expired_qty",
    "damaged_qty",
    "closing_qty",
    "on_order_qty",
    "stockout_hours",
]:
    inventory[column] = pd.to_numeric(
        inventory[column], errors="coerce"
    ).fillna(0)

# Datos del producto para mostrar nombres legibles.
product_info = products[
    ["sku_key", "product_name", "category", "unit_cost"]
].drop_duplicates("sku_key")

# Ultimo registro disponible por tienda y producto.
latest_inventory = (
    inventory.sort_values("date")
    .drop_duplicates(["store_id", "sku_key"], keep="last")
    .merge(product_info, on="sku_key", how="left")
)

latest_inventory["product_name"] = (
    latest_inventory["product_name"].fillna(
        latest_inventory["sku"]
    )
)

# Estimacion sencilla: ventas de los ultimos 28 dias,
# divididas entre cuatro para aproximar la demanda semanal.
latest_sales_date = sales["date"].max()
recent_sales = sales[
    sales["date"] > latest_sales_date - pd.Timedelta(days=28)
]

weekly_demand = (
    recent_sales.groupby(["store_id", "sku_key"])["units_sold"]
    .sum()
    .rename("forecast_units")
    .reset_index()
)

latest_inventory = latest_inventory.merge(
    weekly_demand,
    on=["store_id", "sku_key"],
    how="left",
)

latest_inventory["forecast_units"] = (
    latest_inventory["forecast_units"].fillna(0)
)

# Clasificacion inicial de inventario.
latest_inventory["available_qty"] = (
    latest_inventory["closing_qty"]
    + latest_inventory["on_order_qty"]
)

latest_inventory["status"] = latest_inventory.apply(
    lambda row: (
        "review_restock"
        if row["forecast_units"] > row["available_qty"]
        else "watch"
        if row["closing_qty"] < row["forecast_units"]
        else "ok"
    ),
    axis=1,
)

# Los datos de ventas y el inventario pueden tener distintos
# formatos de SKU; ambos se unifican mediante sku_key.


def validate_store(store_id):
    known = set(sales["store_id"].astype(str))
    known.update(inventory["store_id"].astype(str))

    if store_id not in known:
        raise HTTPException(
            status_code=404,
            detail=f"No hay datos para la tienda {store_id}",
        )


def json_number(value):
    if pd.isna(value):
        return 0
    return float(value)


# --------------------------------------------------
# Inicio y estado de la API
# --------------------------------------------------

@app.get("/")
def root():
    return {
        "message": "Retail Intelligence API funcionando",
        "docs": "/docs",
        "endpoints": [
            "/api/dashboard",
            "/api/inventory",
            "/api/recommendations",
        ],
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "sales_rows": len(sales),
        "inventory_rows": len(inventory),
    }


# --------------------------------------------------
# 1. Dashboard
# --------------------------------------------------

@app.get("/api/dashboard")
def dashboard(store_id: str = "S001"):
    validate_store(store_id)

    store_sales = sales[sales["store_id"] == store_id]

    # Mostrar el mes mas reciente presente en los datos.
    end_date = store_sales["date"].max()
    start_date = end_date.replace(day=1)

    period_sales = store_sales[
        (store_sales["date"] >= start_date)
        & (store_sales["date"] <= end_date)
    ]

    daily = (
        period_sales.groupby("date", as_index=False)["net_sales"]
        .sum()
        .sort_values("date")
    )

    store_inventory = latest_inventory[
        latest_inventory["store_id"] == store_id
    ]

    recommendations_count = int(
        (store_inventory["status"] == "review_restock").sum()
    )

    return {
        "store_id": store_id,
        "period": {
            "from": start_date.strftime("%Y-%m-%d"),
            "to": end_date.strftime("%Y-%m-%d"),
        },
        "metrics": {
            "net_sales": round(
                json_number(period_sales["net_sales"].sum()), 2
            ),
            "units_sold": int(period_sales["units_sold"].sum()),
            "low_stock_products": int(
                (store_inventory["status"] == "review_restock").sum()
            ),
            "recommendations_count": recommendations_count,
        },
        "sales_trend": [
            {
                "date": row["date"].strftime("%Y-%m-%d"),
                "net_sales": round(json_number(row["net_sales"]), 2),
            }
            for _, row in daily.iterrows()
        ],
    }


# --------------------------------------------------
# 2. Inventario y demanda estimada
# --------------------------------------------------

@app.get("/api/inventory")
def get_inventory(store_id: str = "S001", limit: int = 100):
    validate_store(store_id)

    if limit < 1 or limit > 500:
        raise HTTPException(
            status_code=400,
            detail="limit debe estar entre 1 y 500",
        )

    data = latest_inventory[
        latest_inventory["store_id"] == store_id
    ].copy()

    data = data.sort_values(
        ["status", "forecast_units"],
        ascending=[True, False],
    ).head(limit)

    items = []

    for _, row in data.iterrows():
        items.append({
            "sku": str(row["sku"]),
            "product_name": str(row["product_name"]),
            "closing_qty": int(row["closing_qty"]),
            "forecast_units": int(math.ceil(row["forecast_units"])),
            "status": str(row["status"]),
        })

    return {
        "store_id": store_id,
        "items": items,
    }


# --------------------------------------------------
# 3. Recomendaciones
# --------------------------------------------------

@app.get("/api/recommendations")
def get_recommendations(store_id: str = "S001"):
    validate_store(store_id)

    data = latest_inventory[
        (latest_inventory["store_id"] == store_id)
        & (latest_inventory["status"] == "review_restock")
    ].copy()

    data = data.sort_values(
        "forecast_units", ascending=False
    )

    recommendations = []

    for _, row in data.iterrows():
        forecast = int(math.ceil(row["forecast_units"]))
        closing = int(row["closing_qty"])
        available = int(row["available_qty"])

        priority = (
            "high"
            if forecast > available * 1.5
            else "medium"
        )

        recommendations.append({
            "sku": str(row["sku"]),
            "action": "review_restock",
            "priority": priority,
            "reason": (
                "La demanda semanal estimada supera "
                "el inventario disponible y lo que esta por llegar."
            ),
            "evidence": {
                "forecast_units": forecast,
                "closing_qty": closing,
                "on_order_qty": int(row["on_order_qty"]),
                "available_qty": available,
            },
        })

    return {
        "store_id": store_id,
        "recommendations": recommendations,
    }



