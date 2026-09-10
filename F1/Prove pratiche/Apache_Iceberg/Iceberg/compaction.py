import json
import boto3
import duckdb
import pyarrow as pa

from pyiceberg.catalog import load_catalog


# ============================================================
# CONFIGURAZIONE
# ============================================================

TABLE_NAME = "test.prodotti"

BUCKET = "lakehouse"
S3_ENDPOINT = "http://localhost:9000"
S3_ACCESS_KEY = "admin"
S3_SECRET_KEY = "admin12345"

METADATA_LOCATION = (
    "s3://lakehouse/test/prodotti/metadata/"
    "00024-d1e69703-6ce0-4208-ab4f-02efe53ed262.metadata.json"
)


# ============================================================
# CATALOGO
# ============================================================

catalog = load_catalog("default")


# ============================================================
# FUNZIONI DI SUPPORTO
# ============================================================

def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name="us-east-1",
    )


def s3_key_from_uri(uri):
    prefix = f"s3://{BUCKET}/"
    if not uri.startswith(prefix):
        raise ValueError(f"URI S3 inatteso: {uri}")

    return uri[len(prefix):]


def read_metadata():
    """
    Legge direttamente il metadata JSON da MinIO.
    Serve per aggirare il problema per cui PyIceberg,
    pur avendo metadata corretti, restituisce current_snapshot() = None.
    """

    client = s3_client()

    key = s3_key_from_uri(METADATA_LOCATION)

    response = client.get_object(
        Bucket=BUCKET,
        Key=key,
    )

    metadata = json.loads(
        response["Body"].read().decode("utf-8")
    )

    return metadata


def get_snapshot_info(metadata):
    """
    Recupera lo snapshot corrente dal metadata JSON.
    """

    current_snapshot_id = metadata.get("current-snapshot-id")

    if current_snapshot_id is None:
        raise RuntimeError(
            "Il metadata JSON non contiene current-snapshot-id"
        )

    current_snapshot = None

    for snapshot in metadata.get("snapshots", []):
        if snapshot["snapshot-id"] == current_snapshot_id:
            current_snapshot = snapshot
            break

    if current_snapshot is None:
        raise RuntimeError(
            f"Snapshot corrente {current_snapshot_id} "
            "non trovato nell'elenco snapshots"
        )

    return current_snapshot


def get_duckdb_stats(metadata_location):
    """
    Conta i file Parquet e i record presenti nello snapshot
    usando DuckDB + MinIO.
    """

    con = duckdb.connect()

    # Configurazione MinIO
    con.execute(
        f"""
        SET s3_endpoint = 'localhost:9000';
        SET s3_access_key_id = '{S3_ACCESS_KEY}';
        SET s3_secret_access_key = '{S3_SECRET_KEY}';
        SET s3_use_ssl = false;
        SET s3_url_style = 'path';
        """
    )

    metadata_sql = metadata_location.replace("'", "''")

    query = f"""
        SELECT
            COUNT(*) AS file_count,
            COALESCE(SUM(record_count), 0) AS record_count
        FROM iceberg_metadata('{metadata_sql}')
    """

    result = con.execute(query).fetchone()

    con.close()

    return int(result[0]), int(result[1])


def print_snapshot(snapshot, title):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)

    print(f"Snapshot ID       : {snapshot['snapshot-id']}")
    print(f"Sequence number   : {snapshot['sequence-number']}")
    print(f"Timestamp         : {snapshot['timestamp-ms']}")
    print(f"Manifest list     : {snapshot['manifest-list']}")

    summary = snapshot.get("summary", {})

    print(f"Operation         : {summary.get('operation')}")
    print(f"Added files       : {summary.get('added-data-files')}")
    print(f"Added records     : {summary.get('added-records')}")
    print(f"Total files       : {summary.get('total-data-files')}")
    print(f"Total records     : {summary.get('total-records')}")


# ============================================================
# INIZIO
# ============================================================

print()
print("=" * 60)
print("             COMPACTION ICEBERG")
print("=" * 60)

print()
print(f"Tabella: {TABLE_NAME}")
print(f"Metadata: {METADATA_LOCATION}")


# ============================================================
# 1. LEGGIAMO IL METADATA RAW
# ============================================================

metadata = read_metadata()

old_snapshot = get_snapshot_info(metadata)

old_snapshot_id = old_snapshot["snapshot-id"]
old_sequence = old_snapshot["sequence-number"]

print_snapshot(
    old_snapshot,
    "SNAPSHOT PRIMA DELLA COMPACTION",
)


# ============================================================
# 2. STATISTICHE BEFORE
# ============================================================

old_file_count, old_record_count = get_duckdb_stats(
    METADATA_LOCATION
)

print()
print("STATO PRIMA DELLA COMPACTION")
print("-" * 60)
print(f"Snapshot ID : {old_snapshot_id}")
print(f"Sequence    : {old_sequence}")
print(f"File attivi : {old_file_count}")
print(f"Record      : {old_record_count}")


if old_file_count <= 1:
    print()
    print("La tabella ha già un solo file attivo.")
    print("Nessuna compaction necessaria.")
    raise SystemExit(0)


# ============================================================
# 3. CARICHIAMO LA TABELLA
# ============================================================

print()
print("Caricamento tabella PyIceberg...")

table = catalog.load_table(TABLE_NAME)

print(f"Metadata location PyIceberg:")
print(table.metadata_location)


# ============================================================
# 4. VERIFICA DEL PROBLEMA current_snapshot()
# ============================================================

pyiceberg_snapshot = table.current_snapshot()

print()

if pyiceberg_snapshot is None:
    print(
        "ATTENZIONE: PyIceberg.current_snapshot() restituisce None."
    )
    print(
        "Il metadata JSON però indica correttamente lo snapshot:"
    )
    print(f"    {old_snapshot_id}")
else:
    print(
        "PyIceberg.current_snapshot() restituisce:"
    )
    print(
        f"    {pyiceberg_snapshot.snapshot_id}"
    )

    if pyiceberg_snapshot.snapshot_id != old_snapshot_id:
        raise RuntimeError(
            "Snapshot PyIceberg diverso dallo snapshot presente "
            "nel metadata JSON."
        )


# ============================================================
# 5. RICARICHIAMO LA TABELLA
# ============================================================

print()
print("Refresh della tabella...")

table.refresh()

print(
    f"Metadata dopo refresh:"
)
print(
    table.metadata_location
)

refreshed_snapshot = table.current_snapshot()

if refreshed_snapshot is not None:
    print(
        f"Snapshot dopo refresh: "
        f"{refreshed_snapshot.snapshot_id}"
    )
else:
    print(
        "current_snapshot() continua a restituire None."
    )

print()


# ============================================================
# 6. LEGGIAMO TUTTI I DATI
# ============================================================

print()
print("Lettura dei dati correnti...")

con = duckdb.connect()

metadata_sql = METADATA_LOCATION.replace("'", "''")

con.execute(
    f"""
    SET s3_endpoint = 'localhost:9000';
    SET s3_access_key_id = '{S3_ACCESS_KEY}';
    SET s3_secret_access_key = '{S3_SECRET_KEY}';
    SET s3_use_ssl = false;
    SET s3_url_style = 'path';
    """
)

metadata_sql = METADATA_LOCATION.replace("'", "''")

query = f"""
    SELECT
        id,
        nome,
        prezzo,
        quantita
    FROM iceberg_scan('{metadata_sql}')
    ORDER BY id
"""

arrow_table = con.execute(query).fetch_arrow_table()

con.close()


# ============================================================
# 7. NORMALIZZIAMO LO SCHEMA ARROW
# ============================================================

arrow_table = pa.table(
    {
        "id": pa.array(
            arrow_table["id"],
            type=pa.int64(),
        ),
        "nome": pa.array(
            arrow_table["nome"],
            type=pa.string(),
        ),
        "prezzo": pa.array(
            arrow_table["prezzo"],
            type=pa.float64(),
        ),
        "quantita": pa.array(
            arrow_table["quantita"],
            type=pa.int64(),
        ),
    },
    schema=pa.schema(
        [
            pa.field(
                "id",
                pa.int64(),
                nullable=False,
            ),
            pa.field(
                "nome",
                pa.string(),
                nullable=True,
            ),
            pa.field(
                "prezzo",
                pa.float64(),
                nullable=True,
            ),
            pa.field(
                "quantita",
                pa.int64(),
                nullable=True,
            ),
        ]
    ),
)


print()
print("Dati letti:")
print(arrow_table)

print()
print(
    f"Record da riscrivere: {arrow_table.num_rows}"
)


if arrow_table.num_rows != old_record_count:
    raise RuntimeError(
        "Il numero di record letto da DuckDB non coincide "
        "con quello dello snapshot corrente."
    )


# ============================================================
# 8. COMPACTION
# ============================================================

print()
print("=" * 60)
print("             AVVIO COMPACTION")
print("=" * 60)

print()
print(
    "Riscrittura di tutti i dati in nuovi file Parquet..."
)

print(
    "ATTENZIONE: non vengono cancellati manualmente "
    "i vecchi file da MinIO."
)

# overwrite con filtro sempre vero:
#
# tutti i dati esistenti vengono sostituiti dai dati
# contenuti in arrow_table.
#
# L'operazione è supportata direttamente dall'API PyIceberg.
table.overwrite(
    arrow_table,
    overwrite_filter="true",
    snapshot_properties={
        "compaction": "true",
        "compaction.previous-snapshot-id": str(
            old_snapshot_id
        ),
    },
)


# ============================================================
# 9. RICARICA DOPO COMPACTION
# ============================================================

print()
print("Compaction completata.")
print("Ricarico la tabella...")

table = catalog.load_table(TABLE_NAME)

table.refresh()


# ============================================================
# 10. RECUPERIAMO IL NUOVO METADATA LOCATION
# ============================================================

new_metadata_location = table.metadata_location

print()
print("=" * 60)
print("METADATA DOPO LA COMPACTION")
print("=" * 60)

print()
print(
    f"Nuovo metadata: {new_metadata_location}"
)


# ============================================================
# 11. LEGGIAMO IL NUOVO SNAPSHOT DAL METADATA
# ============================================================

# Convertiamo la nuova URI in bucket/key

client = s3_client()

new_key = s3_key_from_uri(
    new_metadata_location
)

response = client.get_object(
    Bucket=BUCKET,
    Key=new_key,
)

new_metadata = json.loads(
    response["Body"].read().decode("utf-8")
)

new_snapshot = get_snapshot_info(
    new_metadata
)

new_snapshot_id = new_snapshot["snapshot-id"]
new_sequence = new_snapshot["sequence-number"]


print_snapshot(
    new_snapshot,
    "SNAPSHOT DOPO LA COMPACTION",
)


# ============================================================
# 12. STATISTICHE AFTER
# ============================================================

new_file_count, new_record_count = get_duckdb_stats(
    new_metadata_location
)

print()
print("=" * 60)
print("             RISULTATO COMPACTION")
print("=" * 60)

print()
print("PRIMA")
print("-" * 60)
print(f"Snapshot ID : {old_snapshot_id}")
print(f"Sequence    : {old_sequence}")
print(f"File attivi : {old_file_count}")
print(f"Record      : {old_record_count}")

print()
print("DOPO")
print("-" * 60)
print(f"Snapshot ID : {new_snapshot_id}")
print(f"Sequence    : {new_sequence}")
print(f"File attivi : {new_file_count}")
print(f"Record      : {new_record_count}")


# ============================================================
# 13. VERIFICHE FINALI
# ============================================================

print()
print("=" * 60)
print("             VERIFICHE FINALI")
print("=" * 60)

errors = []


if new_snapshot_id == old_snapshot_id:
    errors.append(
        "Lo snapshot ID non è cambiato."
    )


if new_sequence <= old_sequence:
    errors.append(
        "Il sequence number non è aumentato."
    )


if new_record_count != old_record_count:
    errors.append(
        "Il numero di record è cambiato."
    )


if new_file_count >= old_file_count:
    print()
    print(
        "ATTENZIONE: il numero di file attivi "
        "non è diminuito."
    )
    print(
        f"Prima: {old_file_count}"
    )
    print(
        f"Dopo : {new_file_count}"
    )


if errors:
    print()

    for error in errors:
        print(f"ERRORE: {error}")

    raise RuntimeError(
        "La compaction non ha prodotto il risultato atteso."
    )


# ============================================================
# 14. RISULTATO
# ============================================================

print()
print("=" * 60)
print("             COMPACTION RIUSCITA")
print("=" * 60)

print()
print(
    f"Snapshot precedente : {old_snapshot_id}"
)

print(
    f"Nuovo snapshot      : {new_snapshot_id}"
)

print(
    f"Sequence precedente : {old_sequence}"
)

print(
    f"Nuovo sequence      : {new_sequence}"
)

print()
print(
    f"File attivi: {old_file_count} -> {new_file_count}"
)

print(
    f"Record:      {old_record_count} -> {new_record_count}"
)

print()
print(
    "I vecchi file Parquet possono ancora essere presenti "
    "fisicamente su MinIO."
)

print(
    "Questo è normale: la compaction modifica lo stato "
    "logico della tabella creando un nuovo snapshot."
)

print()
print("=" * 60)
print("                    FINE")
print("=" * 60)