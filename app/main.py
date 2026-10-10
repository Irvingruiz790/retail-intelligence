from pathlib import Path
import math
import re

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


# ==================================================
# 1. Configuración
# ==================================================

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT.parent / "dataset-hacktahton-road2tech"
MODEL_PATH = ROOT / "models" / "demand_model.joblib"

app = FastAPI(
    title="Retail Intelligence API",
    description="Dashboard, demanda e inventario para tiendas retail",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================================================
# 2. Funciones auxiliares
# ==================================================

def normalize_sku(value):
    """Unifica formatos como SKU-100101 y SKU100101."""
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def load_csv(filename, dates=None):
    path = DATA_DIR / filename

    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")

    return pd.read_csv(path, parse_dates=dates or [])


def json_number(value):
    if pd.isna(value):
        return 0.0
    return float(value)


def validate_store(store_id):
    known = set(sales["store_id"].astype(str))
    known.update(inventory["store_id"].astype(str))

    if str(store_id) not in known:
        raise HTTPException(
            status_code=404,
            detail=f"No hay datos para la tienda {store_id}",
        )


# ==================================================
# 3. Cargar el modelo y los datos
# ==================================================

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"No se encontró el modelo entrenado: {MODEL_PATH}"
    )

model_bundle = joblib.load(MODEL_PATH)
model = model_bundle["model"]
features = model_bundle["features"]

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

# Normalizar identificadores de productos.
sales["sku_key"] = sales["sku"].map(normalize_sku)
inventory["sku_key"] = inventory["sku"].map(normalize_sku)
products["sku_key"] = products["sku"].map(normalize_sku)

# Normalizar columnas numéricas de ventas.
for column in ["units_sold", "net_sales"]:
    sales[column] = pd.to_numeric(
        sales[column], errors="coerce"
    ).fillna(0)

# Normalizar columnas numéricas de inventario.
inventory_columns = [
    "opening_qty",
    "received_qty",
    "units_sold",
    "expired_qty",
    "damaged_qty",
    "closing_qty",
    "on_order_qty",
    "stockout_hours",
]

for column in inventory_columns:
    inventory[column] = pd.to_numeric(
        inventory[column], errors="coerce"
    ).fillna(0)

# Información legible de los productos.
product_info = products[
    ["sku_key", "product_name", "category", "unit_cost"]
].drop_duplicates("sku_key")

# Último inventario disponible por tienda y producto.
latest_inventory = (
    inventory.sort_values("date")
    .drop_duplicates(
        ["store_id", "sku_key"],
        keep="last",
    )
    .merge(product_info, on="sku_key", how="left")
)

latest_inventory["product_name"] = (
    latest_inventory["product_name"].fillna(
        latest_inventory["sku"]
    )
)

# ==================================================
# 4. Estimación de demanda semanal de referencia
# ==================================================

latest_sales_date = sales["date"].max()

recent_sales = sales[
    sales["date"] > latest_sales_date - pd.Timedelta(days=28)
]

# Ventas de 28 días / 4 = estimación semanal.
weekly_demand = (
    recent_sales.groupby(["store_id", "sku_key"])["units_sold"]
    .sum()
    .div(4)
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


# ==================================================
# 5. Inicio y estado de la API
# ==================================================

@app.get("/")
def root():
    return {
        "message": "Retail Intelligence API funcionando",
        "docs": "/docs",
        "endpoints": [
            "/health",
            "/api/dashboard",
            "/api/inventory",
            "/api/recommendations",
            "/api/forecast",
            "/api/forecast/global",
        ],
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "sales_rows": len(sales),
        "inventory_rows": len(inventory),
        "model_loaded": model is not None,
    }


# ==================================================
# 6. Dashboard
# ==================================================

@app.get("/api/dashboard")
def dashboard(store_id: str = "S001"):
    validate_store(store_id)

    store_sales = sales[
        sales["store_id"].astype(str) == str(store_id)
    ]

    if store_sales.empty:
        raise HTTPException(
            status_code=404,
            detail="No hay ventas para esta tienda.",
        )

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
        latest_inventory["store_id"].astype(str) == str(store_id)
    ]

    low_stock = int(
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
            "low_stock_products": low_stock,
            "recommendations_count": low_stock,
        },
        "sales_trend": [
            {
                "date": row["date"].strftime("%Y-%m-%d"),
                "net_sales": round(
                    json_number(row["net_sales"]), 2
                ),
            }
            for _, row in daily.iterrows()
        ],
    }


# ==================================================
# 7. Inventario
# ==================================================

@app.get("/api/inventory")
def get_inventory(store_id: str = "S001", limit: int = 100):
    validate_store(store_id)

    if limit < 1 or limit > 500:
        raise HTTPException(
            status_code=400,
            detail="limit debe estar entre 1 y 500",
        )

    data = latest_inventory[
        latest_inventory["store_id"].astype(str) == str(store_id)
    ].copy()

    # Mostrar primero los productos que requieren revisión.
    priority_order = {
        "review_restock": 0,
        "watch": 1,
        "ok": 2,
    }

    data["_priority"] = data["status"].map(priority_order)

    data = data.sort_values(
        ["_priority", "forecast_units"],
        ascending=[True, False],
    ).head(limit)

    items = []

    for _, row in data.iterrows():
        items.append({
            "sku": str(row["sku"]),
            "product_name": str(row["product_name"]),
            "closing_qty": int(row["closing_qty"]),
            "on_order_qty": int(row["on_order_qty"]),
            "available_qty": int(row["available_qty"]),
            "forecast_units": round(
                json_number(row["forecast_units"]), 2
            ),
            "status": str(row["status"]),
        })

    return {
        "store_id": store_id,
        "items": items,
        "count": len(items),
    }


# ==================================================
# 8. Pronóstico de demanda por tienda
# ==================================================

@app.get("/api/forecast")
def get_forecast(
    store_id: str = "S001",
    date: str = "2026-10-01",
    horizon: int = 1,
):
    validate_store(store_id)

    if horizon not in (1, 7):
        raise HTTPException(
            status_code=400,
            detail="horizon debe ser 1 o 7",
        )

    try:
        target_date = pd.Timestamp(date).normalize()
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="date debe tener formato YYYY-MM-DD",
        )

    if target_date <= latest_sales_date:
        raise HTTPException(
            status_code=400,
            detail=(
                "La fecha debe ser posterior al historial disponible: "
                + latest_sales_date.strftime("%Y-%m-%d")
            ),
        )

    # Solo pronosticar productos que aparecen en el inventario
    # de esta tienda.
    eligible_skus = set(
        latest_inventory.loc[
            latest_inventory["store_id"].astype(str)
            == str(store_id),
            "sku_key",
        ]
    )

    store_sales = sales[
        (sales["store_id"].astype(str) == str(store_id))
        & (sales["sku_key"].isin(eligible_skus))
    ]

    results = []

    for sku_key, group in store_sales.groupby("sku_key"):
        group = group.sort_values("date")

        history = (
            group.set_index("date")["units_sold"]
            .groupby(level=0)
            .sum()
            .sort_index()
        )

        if history.empty or len(history) < 14:
            continue

        # No tratar días ausentes como ventas cero sin evidencia.
        daily_index = pd.date_range(
            history.index.min(),
            history.index.max(),
            freq="D",
        )

        if len(history.index) != len(daily_index):
            continue

        sku_history = history.astype(float).copy()
        predictions = []
        end_date = target_date + pd.Timedelta(days=horizon - 1)

        while sku_history.index.max() < end_date:
            next_date = sku_history.index.max() + pd.Timedelta(days=1)

            row = {
                "day_of_week": next_date.dayofweek,
                "day_of_month": next_date.day,
                "month": next_date.month,
                "lag_7": sku_history.iloc[-7],
                "lag_14": sku_history.iloc[-14],
                "rolling_mean_7": sku_history.iloc[-7:].mean(),
            }

            X = pd.DataFrame([row], columns=features)
            prediction = max(0.0, float(model.predict(X)[0]))

            sku_history.loc[next_date] = prediction

            if target_date <= next_date <= end_date:
                predictions.append({
                    "date": next_date.strftime("%Y-%m-%d"),
                    "forecast_units": round(prediction, 2),
                })

        if not predictions:
            continue

        results.append({
            "sku": str(group["sku"].iloc[-1]),
            "daily_forecast": predictions,
            "total_forecast": round(
                sum(item["forecast_units"] for item in predictions),
                2,
            ),
        })

    return {
        "store_id": store_id,
        "start_date": target_date.strftime("%Y-%m-%d"),
        "horizon_days": horizon,
        "products_count": len(results),
        "forecasts": results,
    }


# ==================================================
# 9. Recomendaciones de reposición
# ==================================================

@app.get("/api/recommendations")
def get_recommendations(store_id: str = "S001"):
    validate_store(store_id)

    forecast_date = (
        latest_sales_date + pd.Timedelta(days=1)
    ).strftime("%Y-%m-%d")

    forecast_data = get_forecast(
        store_id=store_id,
        date=forecast_date,
        horizon=7,
    )

    inventory_by_sku = (
        latest_inventory[
            latest_inventory["store_id"].astype(str) == str(store_id)
        ]
        .drop_duplicates("sku_key")
        .set_index("sku_key")
    )

    recommendations = []

    for item in forecast_data["forecasts"]:
        sku_key = normalize_sku(item["sku"])

        if sku_key not in inventory_by_sku.index:
            continue

        stock = inventory_by_sku.loc[sku_key]

        demand = float(item["total_forecast"])
        closing = int(stock["closing_qty"])
        on_order = int(stock["on_order_qty"])
        available = closing + on_order

        recommended_quantity = max(
            0,
            math.ceil(demand - available),
        )

        if recommended_quantity == 0:
            continue

        priority = (
            "high"
            if available < demand * 0.5
            else "medium"
        )

        recommendations.append({
            "sku": str(item["sku"]),
            "product_name": str(stock["product_name"]),
            "action": "review_restock",
            "priority": priority,
            "recommended_quantity": recommended_quantity,
            "reason": (
                "La demanda pronosticada para 7 días "
                "supera el inventario disponible."
            ),
            "evidence": {
                "forecast_units": round(demand, 2),
                "closing_qty": closing,
                "on_order_qty": on_order,
                "available_qty": available,
            },
        })

    recommendations.sort(
        key=lambda item: (
            item["priority"] != "high",
            -item["recommended_quantity"],
        )
    )

    return {
        "store_id": store_id,
        "forecast_start_date": forecast_date,
        "horizon_days": 7,
        "recommendations_count": len(recommendations),
        "recommendations": recommendations,
    }


# ==================================================
# 10. Pronóstico global para todas las tiendas
# ==================================================

@app.get("/api/forecast/global")
def get_global_forecast(date: str = "2026-10-11"):
    try:
        target_date = pd.Timestamp(date).normalize()
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="date debe tener formato YYYY-MM-DD",
        )

    if target_date <= latest_sales_date:
        raise HTTPException(
            status_code=400,
            detail=(
                "La fecha inicial debe ser posterior al historial: "
                + latest_sales_date.strftime("%Y-%m-%d")
            ),
        )

    horizon = 7
    end_date = target_date + pd.Timedelta(days=horizon - 1)

    series_list = []
    excluded_short = 0
    excluded_stale = 0
    excluded_large_gaps = 0
    imputed_days = 0

    for (store_id, sku_key), group in sales.groupby(
        ["store_id", "sku_key"]
    ):
        history = (
            group.groupby("date")["units_sold"]
            .sum()
            .sort_index()
            .astype(float)
        )

        if len(history) < 14:
            excluded_short += 1
            continue

        if history.index.max() != latest_sales_date:
            excluded_stale += 1
            continue

        expected_dates = pd.date_range(
            history.index.min(),
            history.index.max(),
            freq="D",
        )

        missing_dates = expected_dates.difference(history.index)

        if len(missing_dates) > 0:
            missing_mask = pd.Series(
                expected_dates.isin(missing_dates),
                index=expected_dates,
            )

            gap_groups = missing_mask.ne(
                missing_mask.shift()
            ).cumsum()

            missing_runs = missing_mask[missing_mask].groupby(
                gap_groups[missing_mask]
            ).size()

            if len(missing_runs) and int(missing_runs.max()) > 3:
                excluded_large_gaps += 1
                continue

            # Imputar los huecos cortos con la mediana observada.
            median_sales = float(history.median())
            history = history.reindex(expected_dates)
            history.loc[missing_dates] = median_sales
            imputed_days += len(missing_dates)

        series_list.append({
            "store_id": str(store_id),
            "sku_key": sku_key,
            "history": history.copy(),
        })

    if not series_list:
        raise HTTPException(
            status_code=404,
            detail="No hay series elegibles para pronosticar.",
        )

    daily_totals = {
        day.strftime("%Y-%m-%d"): 0.0
        for day in pd.date_range(
            target_date,
            end_date,
            freq="D",
        )
    }

    current_date = latest_sales_date

    while current_date < end_date:
        next_date = current_date + pd.Timedelta(days=1)
        batch_rows = []

        for item in series_list:
            history = item["history"]

            batch_rows.append({
                "day_of_week": next_date.dayofweek,
                "day_of_month": next_date.day,
                "month": next_date.month,
                "lag_7": history.iloc[-7],
                "lag_14": history.iloc[-14],
                "rolling_mean_7": history.iloc[-7:].mean(),
            })

        X = pd.DataFrame(batch_rows, columns=features)
        predictions = model.predict(X)

        for item, prediction in zip(series_list, predictions):
            prediction = max(0.0, float(prediction))
            item["history"].loc[next_date] = prediction

            if target_date <= next_date <= end_date:
                key = next_date.strftime("%Y-%m-%d")
                daily_totals[key] += prediction

        current_date = next_date

    daily_forecast = [
        {
            "date": day,
            "forecast_units": round(total, 2),
        }
        for day, total in daily_totals.items()
    ]

    return {
        "scope": "all_stores",
        "start_date": target_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "horizon_days": horizon,
        "stores_count": len({
            item["store_id"] for item in series_list
        }),
        "store_product_series_count": len(series_list),
        "products_count": len({
            item["sku_key"] for item in series_list
        }),
        "data_through": latest_sales_date.strftime("%Y-%m-%d"),
        "data_quality": {
            "imputation_method": "median_per_store_product",
            "imputed_missing_days": imputed_days,
            "excluded_short_history": excluded_short,
            "excluded_stale_history": excluded_stale,
            "excluded_large_gaps": excluded_large_gaps,
        },
        "daily_forecast": daily_forecast,
        "total_forecast": round(
            sum(daily_totals.values()), 2
        ),
    }