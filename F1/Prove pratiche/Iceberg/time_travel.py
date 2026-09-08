import duckdb

from pyiceberg.catalog import load_catalog


# ============================================================
# 1. CARICAMENTO TABELLA ICEBERG
# ============================================================

catalog = load_catalog("default")

table = catalog.load_table("test.prodotti")

metadata = table.metadata_location

print("Metadata location:")
print(metadata)


# ============================================================
# 2. CONNESSIONE DUCKDB
# ============================================================

conn = duckdb.connect()

conn.execute("LOAD httpfs")
conn.execute("LOAD iceberg")


# ============================================================
# 3. CONFIGURAZIONE MINIO / S3
# ============================================================

conn.execute("""
SET s3_endpoint='localhost:9000';
SET s3_access_key_id='admin';
SET s3_secret_access_key='admin12345';
SET s3_use_ssl=false;
SET s3_url_style='path';
""")


# ============================================================
# 4. LETTURA DEGLI SNAPSHOT
# ============================================================

#print("\n================ SNAPSHOTS ================\n")

snapshots = conn.execute(
    f"SELECT * FROM iceberg_snapshots('{metadata}')"
).fetchdf()

#print(snapshots)


# ============================================================
# 5. LETTURA DELLA TABELLA ATTUALE
# ============================================================

print("\n================ DATI ATTUALI ================\n")

risultato = conn.execute(f"""
    SELECT *
    FROM iceberg_scan('{metadata}')
    ORDER BY id
""").fetchdf()

print(risultato)


# ============================================================
# 6. PRENDIAMO GLI SNAPSHOT DISPONIBILI
# ============================================================

print("\n================ SNAPSHOT ID ================\n")

snapshot_ids = snapshots["snapshot_id"].tolist()

for i, snapshot_id in enumerate(snapshot_ids):
    print(f"{i}: {snapshot_id}")


# ============================================================
# 7. TIME TRAVEL
# ============================================================

if len(snapshot_ids) >= 2:

    # Prendiamo il penultimo snapshot
    snapshot_precedente = snapshot_ids[5]

    print("\n================ TIME TRAVEL ================\n")
    print("Snapshot utilizzato:")
    print(snapshot_precedente)

    risultato_time_travel = conn.execute(f"""
        SELECT *
        FROM iceberg_scan(
            '{metadata}',
            snapshot_from_id={snapshot_precedente}
        )
        ORDER BY id
    """).fetchdf()

    print("\nDati dello snapshot precedente:\n")
    print(risultato_time_travel)

else:
    print("\nNon ci sono abbastanza snapshot per fare Time Travel.")