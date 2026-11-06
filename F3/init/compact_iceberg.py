import os
from pyiceberg.catalog.sql import SqlCatalog

NOME_TABELLA = "iot.letture_10m"


def get_catalog():
    return SqlCatalog(
        "default",
        uri=os.environ.get("CATALOG_URI", "postgresql+psycopg2://admin:postgres@localhost:5432/progetto_db?options=-csearch_path%3Diceberg_catalog"),
        warehouse=os.environ.get("WAREHOUSE", "warehouse"),
        **{
            "s3.endpoint": os.environ["S3_ENDPOINT"],
            "s3.access-key-id": os.environ["S3_ACCESS_KEY"],
            "s3.secret-access-key": os.environ["S3_SECRET_KEY"],
            "s3.region": os.environ.get("S3_REGION", "us-east-1"),
            "s3.path-style-access": "true",
        },
    )


def statistiche(table):
    files = table.inspect.files().to_pylist()

    return {
        "numero_file": len(files),
        "numero_righe": sum(f["record_count"] for f in files),
        "dimensione_bytes": sum(
            f["file_size_in_bytes"] for f in files
        ),
    }


def esegui_compaction():
    catalog = get_catalog()
    table = catalog.load_table(NOME_TABELLA)

    print(f"\nTabella: {NOME_TABELLA}")

    # Procedura prevista per una tabella non partizionata
    if table.spec().fields:
        raise RuntimeError(
            "Questa procedura è prevista per tabelle non partizionate."
        )

    # Verifica che non siano presenti delete file
    files = table.inspect.files().to_pylist()

    if any(f["content"] != 0 for f in files):
        raise RuntimeError(
            "Sono presenti delete file: procedura interrotta."
        )

    # 1. Stato iniziale
    prima = statistiche(table)
    snapshot_prima = table.current_snapshot()

    if snapshot_prima is None:
        raise RuntimeError("La tabella non ha uno snapshot corrente.")

    print("\n--- PRIMA ---")
    print(f"Snapshot: {snapshot_prima.snapshot_id}")
    print(f"File: {prima['numero_file']}")
    print(f"Righe: {prima['numero_righe']}")
    print(
        f"Dimensione: "
        f"{prima['dimensione_bytes'] / 1024**2:.2f} MiB"
    )

    if prima["numero_file"] <= 1:
        print("Compaction non necessaria.")
        return

    # 2. Lettura dei dati
    print("\nLettura dati Iceberg...")

    dati = table.scan().to_arrow()

    if dati.num_rows != prima["numero_righe"]:
        raise RuntimeError("Conteggio righe non coerente.")

    print(f"Righe lette: {dati.num_rows}")

    # 3. Riscrittura
    print("\nAvvio riscrittura dei Parquet...")

    table.overwrite(
        dati,
        snapshot_properties={
            "compaction": "true",
            "compaction.type": "full-rewrite",
        },
    )

    # 4. Ricarica tabella
    table = catalog.load_table(NOME_TABELLA)

    dopo = statistiche(table)
    snapshot_dopo = table.current_snapshot()

    # 5. Verifica
    print("\n--- DOPO ---")
    print(f"Snapshot: {snapshot_dopo.snapshot_id}")
    print(f"File: {dopo['numero_file']}")
    print(f"Righe: {dopo['numero_righe']}")
    print(
        f"Dimensione: "
        f"{dopo['dimensione_bytes'] / 1024**2:.2f} MiB"
    )

    if prima["numero_righe"] != dopo["numero_righe"]:
        raise RuntimeError("ERRORE: numero di righe modificato.")

    if snapshot_prima.snapshot_id == snapshot_dopo.snapshot_id:
        raise RuntimeError("ERRORE: snapshot non aggiornato.")

    print("\n--- RISULTATO ---")
    print(
        f"File: {prima['numero_file']} "
        f"-> {dopo['numero_file']}"
    )
    print(f"Righe invariati: {dopo['numero_righe']}")

    if dopo["numero_file"] < prima["numero_file"]:
        print("Compaction riuscita: file attivi ridotti.")
    else:
        print("Riscrittura completata, ma file non ridotti.")

    print("\nI vecchi Parquet possono rimanere su MinIO.")
    print("Iceberg li conserva per gli snapshot precedenti.")


if __name__ == "__main__":
    esegui_compaction()
