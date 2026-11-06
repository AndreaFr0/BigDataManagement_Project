"""
Carica i CSV in tabelle Iceberg (file Parquet su MinIO, catalogo su Postgres).

Ordine delle operazioni:
  1. attende MinIO e crea il bucket (se manca)
  2. attende Postgres e inizializza il catalogo Iceberg
  3. per ogni CSV in DATA_DIR crea la tabella iot.<nome_file> e la popola a blocchi

Idempotente: se la tabella ha gia' dei dati viene saltata, quindi un riavvio
del container non duplica le righe.
"""
import os
import sys
import time
from pathlib import Path

import duckdb
import pyarrow as pa
import s3fs
from pyiceberg.catalog.sql import SqlCatalog

CATALOG_URI = os.environ["CATALOG_URI"]
WAREHOUSE = os.environ["WAREHOUSE"]
S3_ENDPOINT = os.environ["S3_ENDPOINT"]
S3_ACCESS_KEY = os.environ["S3_ACCESS_KEY"]
S3_SECRET_KEY = os.environ["S3_SECRET_KEY"]
S3_REGION = os.environ.get("S3_REGION", "us-east-1")

BUCKET = WAREHOUSE.replace("s3://", "").strip("/").split("/")[0]
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
CSV_PATTERN = os.environ.get("CSV_PATTERN", "*.csv")
NAMESPACE = os.environ.get("ICEBERG_NAMESPACE", "iot")
CHUNK_ROWS = int(os.environ.get("CHUNK_ROWS", "1000000"))
WAIT_TIMEOUT = int(os.environ.get("WAIT_TIMEOUT", "1800"))  # secondi


def retry(description, fn, timeout=WAIT_TIMEOUT, delay=5):
    """Esegue fn() finche' non riesce o scade il timeout."""
    start = time.time()
    while True:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            if time.time() - start > timeout:
                print(f"[ERRORE] {description}: timeout ({exc})", flush=True)
                raise
            print(f"[attesa] {description} non pronto: {exc}", flush=True)
            time.sleep(delay)


def ensure_bucket():
    fs = s3fs.S3FileSystem(
        key=S3_ACCESS_KEY,
        secret=S3_SECRET_KEY,
        client_kwargs={"endpoint_url": S3_ENDPOINT, "region_name": S3_REGION},
    )
    if not fs.exists(BUCKET):
        fs.mkdir(BUCKET)
        print(f"[minio] bucket '{BUCKET}' creato", flush=True)
    else:
        print(f"[minio] bucket '{BUCKET}' gia' presente", flush=True)


def get_catalog():
    catalog = SqlCatalog(
        "default",
        uri=CATALOG_URI,
        warehouse=WAREHOUSE,
        **{
            "s3.endpoint": S3_ENDPOINT,
            "s3.access-key-id": S3_ACCESS_KEY,
            "s3.secret-access-key": S3_SECRET_KEY,
            "s3.region": S3_REGION,
            "s3.path-style-access": "true",
        },
    )
    catalog.create_tables()  # crea le tabelle di sistema del catalogo (idempotente)
    return catalog


def load_csv(catalog, csv_path: Path):
    ident = f"{NAMESPACE}.{csv_path.stem.lower()}"

    if catalog.table_exists(ident):
        existing = catalog.load_table(ident)
        if existing.current_snapshot() is not None:
            print(f"[skip] {ident} contiene gia' dati", flush=True)
            return

    print(f"[carico] {csv_path.name} -> {ident}", flush=True)

    # DuckDB legge il CSV in streaming e deduce i tipi su tutto il file
    con = duckdb.connect()
    rel = con.sql(
        f"SELECT * FROM read_csv('{csv_path}', header=true, sample_size=-1)"
    )
    reader = rel.to_arrow_reader(batch_size=CHUNK_ROWS)

    table = catalog.create_table_if_not_exists(ident, schema=reader.schema)

    total = 0
    buffer = []
    buffered = 0
    for batch in reader:
        buffer.append(batch)
        buffered += batch.num_rows
        if buffered >= CHUNK_ROWS:
            table.append(pa.Table.from_batches(buffer, schema=reader.schema))
            total += buffered
            print(f"  {ident}: {total} righe scritte", flush=True)
            buffer, buffered = [], 0
    if buffer:
        table.append(pa.Table.from_batches(buffer, schema=reader.schema))
        total += buffered

    print(f"[ok] {ident}: {total} righe, location {table.location()}", flush=True)


def main():
    csv_files = sorted(DATA_DIR.glob(CSV_PATTERN))
    if not csv_files:
        print(f"[ERRORE] nessun file '{CSV_PATTERN}' in {DATA_DIR}", flush=True)
        sys.exit(1)

    retry("MinIO", ensure_bucket)
    catalog = retry("catalogo Postgres", get_catalog)
    catalog.create_namespace_if_not_exists(NAMESPACE)

    for csv_path in csv_files:
        load_csv(catalog, csv_path)

    print("[fine] caricamento completato", flush=True)


if __name__ == "__main__":
    main()
