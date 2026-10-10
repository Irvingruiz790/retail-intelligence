
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error


# ============================================================
# 1. RUTAS DEL PROYECTO
# ============================================================

# Carpeta raíz del repositorio: retail-intelligence/
ROOT = Path(__file__).resolve().parent.parent

# Dataset ubicado fuera del repositorio, dentro de hackaton/
DATA_PATH = (
    ROOT.parent
    / "dataset-hacktahton-road2tech"
    / "sales_model_baseline.csv"
)

# Carpeta donde guardaremos el modelo entrenado
MODEL_DIR = ROOT / "models"
MODEL_PATH = MODEL_DIR / "demand_model.joblib"


# ============================================================
# 2. CARGAR DATOS
# ============================================================

print("Cargando dataset...")

if not DATA_PATH.exists():
    raise FileNotFoundError(
        f"No se encontró el dataset en:\n{DATA_PATH}\n"
        "Verifica el nombre de la carpeta y del archivo CSV."
    )

df = pd.read_csv(DATA_PATH, parse_dates=["date"])

df = df.sort_values(
    ["store_id", "sku", "date"]
).copy()

print(f"Registros cargados: {len(df):,}")
print(f"Tiendas: {df['store_id'].nunique()}")
print(f"Productos: {df['sku'].nunique()}")
print(
    f"Periodo: {df['date'].min().date()} "
    f"a {df['date'].max().date()}"
)


# ============================================================
# 3. CREAR VARIABLES DE CALENDARIO
# ============================================================

print("\nCreando variables de calendario...")

df["day_of_week"] = df["date"].dt.dayofweek
df["day_of_month"] = df["date"].dt.day
df["month"] = df["date"].dt.month


# ============================================================
# 4. CREAR VARIABLES DE HISTORIAL DE VENTAS
# ============================================================

print("Calculando historial de ventas...")

groups = df.groupby(["store_id", "sku"])["units_sold"]

# Ventas de 7 y 14 registros anteriores del mismo producto
# en la misma tienda.
df["lag_7"] = groups.shift(7)
df["lag_14"] = groups.shift(14)

# Promedio de los 7 registros anteriores, sin incluir
# las ventas del día que queremos predecir.
df["rolling_mean_7"] = groups.transform(
    lambda s: s.shift(1).rolling(
        window=7,
        min_periods=7
    ).mean()
)

features = [
    "day_of_week",
    "day_of_month",
    "month",
    "lag_7",
    "lag_14",
    "rolling_mean_7",
]

# Eliminar filas que no tienen suficiente historial
df = df.dropna(
    subset=features + ["units_sold"]
).copy()

if df.empty:
    raise ValueError(
        "No quedaron registros después de calcular "
        "las variables de historial."
    )

# 5. SEPARAR ENTRENAMIENTO Y PRUEBA POR FECHA

print("\nSeparando entrenamiento y prueba...")

# Reservamos los últimos 28 días como periodo de evaluación.
cutoff = df["date"].max() - pd.Timedelta(days=28)

train = df[df["date"] <= cutoff].copy()
test = df[df["date"] > cutoff].copy()

if train.empty or test.empty:
    raise ValueError(
        "No hay suficientes datos para separar "
        "entrenamiento y prueba."
    )

X_train = train[features]
y_train = train["units_sold"]

X_test = test[features]
y_test = test["units_sold"]

print(f"Filas de entrenamiento: {len(train):,}")
print(f"Filas de prueba: {len(test):,}")
print(f"Fecha límite: {cutoff.date()}")


# ============================================================
# 6. ENTRENAR MODELO
# ============================================================

print("\nEntrenando Random Forest...")

model = RandomForestRegressor(
    n_estimators=100,
    min_samples_leaf=3,
    random_state=42,
    n_jobs=-1,
)

model.fit(X_train, y_train)

print("Entrenamiento terminado.")


# ============================================================
# 7. EVALUAR RESULTADOS
# ============================================================

print("\nEvaluando modelo...")

# Referencia sencilla: asumir que se venderá lo mismo
# que en el séptimo registro anterior.
baseline = test["lag_7"].clip(lower=0)

# Predicciones del modelo, sin ventas negativas.
predictions = np.clip(
    model.predict(X_test),
    0,
    None,
)

mae_baseline = mean_absolute_error(y_test, baseline)
mae_model = mean_absolute_error(y_test, predictions)

rmse_model = np.sqrt(
    mean_squared_error(y_test, predictions)
)

print("\n========== RESULTADOS ==========")
print(f"MAE referencia (lag 7): {mae_baseline:.3f}")
print(f"MAE Random Forest:       {mae_model:.3f}")
print(f"RMSE Random Forest:      {rmse_model:.3f}")

if mae_model < mae_baseline:
    print("El modelo mejora el MAE frente a la referencia.")
else:
    print(
        "El modelo no mejora el MAE frente a la referencia. "
        "Hay que revisar las variables o probar otro enfoque."
    )


# ============================================================
# 8. GUARDAR MODELO Y METADATOS
# ============================================================

print("\nGuardando modelo...")

MODEL_DIR.mkdir(parents=True, exist_ok=True)

joblib.dump(
    {
        "model": model,
        "features": features,
    },
    MODEL_PATH,
)

print(f"Modelo guardado en: {MODEL_PATH}")
print("\nProceso completado.")
