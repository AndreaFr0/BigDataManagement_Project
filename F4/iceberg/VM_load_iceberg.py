
import sys
import time
from pathlib import Path

import duckdb
import pyarrow as pa
import s3fs
from pyiceberg.catalog.sql import SqlCatalog


CATALOG_URI = (
    "postgresql+psycopg2://admin:postgres"
    "@localhost:5432/progetto_db"
    "?options=-c%20search_path%3Diceberg_catalog"
)


BUCKET = "warehouse"
WAREHOUSE = f"s3://{BUCKET}"

S3_ENDPOINT = "http://localhost:9000"
S3_ACCESS_KEY = "admin"
S3_SECRET_KEY = "admin12345"
S3_REGION = "us-east-1"

NAMESPACE = "benchmark"

CHUNK_ROWS = 1000000
WAIT_TIMEOUT = 1800

CSV_FILES = {
    "letture_1M": Path("../../letture/data/letture_1M.csv"),
    "letture_10M": Path("../../letture/data/letture_10M.csv"),
}


def retry(description, fn, timeout=WAIT_TIMEOUT, delay=5):
    """Esegue fn() finche' non riesce o scade il timeout."""

    start = time.time()

    while True:
        try:
            return fn()

        except Exception as exc:

            if time.time() - start > timeout:
                print(
                    f"[ERRORE] {description}: timeout ({exc})",
                    flush=True
                )
                raise

            print(
                f"[attesa] {description} non pronto: {exc}",
                flush=True
            )

            time.sleep(delay)


def ensure_bucket():

    fs = s3fs.S3FileSystem(
        key=S3_ACCESS_KEY,
        secret=S3_SECRET_KEY,
        client_kwargs={
            "endpoint_url": S3_ENDPOINT,
            "region_name": S3_REGION
        }
    )

    if not fs.exists(BUCKET):

        fs.mkdir(BUCKET)

        print(
            f"[minio] bucket '{BUCKET}' creato",
            flush=True
        )

    else:

        print(
            f"[minio] bucket '{BUCKET}' gia' presente",
            flush=True
        )


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

    # Crea le tabelle di sistema se non esistono
    catalog.create_tables()

    return catalog


def normalize_timestamp_schema(schema):
    """Converte i timestamp con timezone non UTC in UTC."""

    fields = []

    for field in schema:
        field_type = field.type

        if (
            pa.types.is_timestamp(field_type)
            and field_type.tz is not None
            and field_type.tz != "UTC"
        ):
            print(
                f"[timezone] {field.name}: "
                f"{field_type.tz} -> UTC",
                flush=True
            )

            field = field.with_type(
                pa.timestamp(field_type.unit, tz="UTC")
            )

        fields.append(field)

    return pa.schema(fields, metadata=schema.metadata)
    

def load_csv(catalog, csv_path: Path, table_name: str):

    # Nome tabella Iceberg
    # PostgreSQL utilizza il nome in minuscolo.
    ident = f"{NAMESPACE}.{table_name.lower()}"

    # Percorso esplicito della tabella su MinIO.
    # Mantiene la M maiuscola nel nome della cartella.
    table_location = (
        f"s3://{BUCKET}/{NAMESPACE}/{table_name}"
    )

    if catalog.table_exists(ident):

        existing = catalog.load_table(ident)

        if existing.current_snapshot() is not None:

            print(
                f"[skip] {ident} contiene gia' dati",
                flush=True
            )

            return

    print(
        f"[carico] {csv_path.name} -> {table_location}",
        flush=True
    )


    con = duckdb.connect()

    try:

        # Lettura del CSV con deduzione dei tipi
        csv_sql_path = csv_path.as_posix().replace("'", "''")

        rel = con.sql(
            f"SELECT * FROM read_csv("
            f"'{csv_sql_path}', "
            f"header=true, "
            f"sample_size=-1)"
        )

        # Lettura a blocchi
        reader = rel.to_arrow_reader(batch_size=CHUNK_ROWS)
        
        # Normalizza lo schema per Iceberg
        iceberg_schema = normalize_timestamp_schema(reader.schema)
        
        table = catalog.create_table_if_not_exists(
            ident,
            schema=iceberg_schema,
            location=table_location
        )
        
        total = 0
        buffer = []
        buffered = 0
        
        for batch in reader:
        
            # Converte i timestamp in UTC
            batch = batch.cast(iceberg_schema)
        
            buffer.append(batch)
            buffered += batch.num_rows
        
            if buffered >= CHUNK_ROWS:
        
                table.append(
                    pa.Table.from_batches(
                        buffer,
                        schema=iceberg_schema
                    )
                )
        
                total += buffered
        
                print(
                    f"  {ident}: {total} righe scritte",
                    flush=True
                )
        
                buffer = []
                buffered = 0

        # Scrive eventuali righe rimanenti
        if buffer:

            table.append(
                pa.Table.from_batches(
                    buffer,
                    schema=iceberg_schema
                )
            )

            total += buffered

        print(
            f"[ok] {ident}: {total} righe, "
            f"location {table.location()}",
            flush=True
        )

    finally:
        con.close()


def main():


    for table_name, csv_path in CSV_FILES.items():

        if not csv_path.is_file():

            print(
                f"[ERRORE] file CSV non trovato: {csv_path}",
                flush=True
            )

            sys.exit(1)

    retry("MinIO", ensure_bucket)

    catalog = retry(
        "catalogo Postgres",
        get_catalog
    )

    catalog.create_namespace_if_not_exists(NAMESPACE)

    print(
        f"[iceberg] namespace '{NAMESPACE}' pronto",
        flush=True
    )

    for table_name, csv_path in CSV_FILES.items():

        load_csv(
            catalog,
            csv_path,
            table_name
        )

    print(
        "[fine] caricamento completato",
        flush=True
    )


if __name__ == "__main__":
    main()
