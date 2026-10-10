
from pathlib import Path
import pandas as pd

DATASET_DIR = (
    Path.home()
    / "hackaton"
    / "dataset-hacktahton-road2tech"
)

archivos = [
    "sales_daily.csv",
    "inventory_daily.csv",
    "products.csv",
    "stores.csv",
    "store_daily_kpis.csv",
    "purchase_orders.csv",
    "prices.csv",
]

for nombre in archivos:
    ruta = DATASET_DIR / nombre

    print(f"\n{'=' * 60}")
    print(f"ARCHIVO: {nombre}")

    df = pd.read_csv(ruta)

    print(f"Filas: {len(df):,}")
    print(f"Columnas: {len(df.columns)}")
    print(f"Filas duplicadas completas: {df.duplicated().sum()}")

    print("\nTipos de datos:")
    print(df.dtypes.to_string())

    print("\nValores faltantes por columna:")
    faltantes = df.isna().sum()
    faltantes = faltantes[faltantes > 0]

    if faltantes.empty:
        print("No hay valores faltantes.")
    else:
        print(faltantes.to_string())

    print("\nEstadísticas numéricas:")

    numericas = df.select_dtypes(include="number")

    if numericas.empty:
        print("No se encontraron valores numericos")

    else: 
        print(numericas.describe().round(2))
