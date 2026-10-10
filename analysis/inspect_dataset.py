from pathlib import Path
import pandas as pd 

# Ubicacion del repositorio del dataset 

DATASET_DIR = Path.home() / "hackaton" / "dataset-hacktahton-road2tech"

#Recorrer los archivos CSV 
for archivo in sorted(DATASET_DIR.glob("*.csv")):
    print(f"\n{'=' * 60}")
    print(f"Archivo: {archivo.name}")

    df = pd.read_csv(archivo, nrows=5)

    print("Columnas: ", df.columns.tolist())
    print("\nPrimeras filas: ")
    print(df.head(2).to_string(index=False))
