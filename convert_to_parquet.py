import pandas as pd
import os

COINS = ["ETH", "SOL", "DOGE"]
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DIRS = ["candles", "detail", "liquid"]

def convert():
    for d in DIRS:
        path = os.path.join(DATA_DIR, d)
        if not os.path.exists(path):
            continue
        for file in os.listdir(path):
            if file.endswith(".csv"):
                csv_path = os.path.join(path, file)
                parquet_path = csv_path.replace(".csv", ".parquet")
                print(f"Converting {file}...")
                df = pd.read_csv(csv_path)
                # Optimize types
                for col in df.columns:
                    if any(x in col.lower() for x in ["time", "date"]):
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                df.to_parquet(parquet_path, index=False)
                print(f"Done: {parquet_path}")

if __name__ == "__main__":
    convert()
