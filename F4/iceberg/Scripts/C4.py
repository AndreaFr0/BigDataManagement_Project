
"""
C4 - CANCELLAZIONE DELLE LETTURE DI UN SENSORE

Per ogni dataset:
1. Individua un sensore
2. Misura righe, file e spazio iniziale
3. Cancella tutte le letture del sensore
4. Misura tempo e variazione dello spazio
5. Verifica la cancellazione nello snapshot corrente
6. Verifica il recupero tramite time travel

ATTENZIONE:
- Modifica le tabelle configurate in common.py
- La cancellazione è persistente
- Non elimina gli snapshot precedenti
"""

import time
from urllib.parse import quote, urlparse

import boto3

from pyiceberg.catalog.sql import SqlCatalog
from pyiceberg.expressions import EqualTo

from common import (
    run,
    TABLES,
    NAMESPACE,
    CATALOG_NAME,
    PG_HOST,
    PG_PORT,
    PG_DB,
    PG_USER,
    PG_PASSWORD,
    PG_SCHEMA,
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_REGION,
    metadata_path,
    duck,
    scan,
)

SENSOR_COLUMN = None
SENSOR_VALUE = None

SENSOR_COLUMNS = (
    "id_sensore",
    "sensore_id",
    "sensor_id",
    "id_sensor",
    "sensore",
    "sensor",
)

WAREHOUSE = "s3://lakehouse"


def get_catalog():

    uri = (
        f"postgresql+psycopg2://"
        f"{quote(PG_USER, safe='')}:"
        f"{quote(PG_PASSWORD, safe='')}"
        f"@{PG_HOST}:{PG_PORT}/{PG_DB}"
        f"?options=-c%20search_path%3D"
        f"{quote(PG_SCHEMA, safe='')}"
    )

    return SqlCatalog(
        CATALOG_NAME,
        uri=uri,
        warehouse=WAREHOUSE,
        **{
            "s3.endpoint": MINIO_ENDPOINT,
            "s3.access-key-id": MINIO_ACCESS_KEY,
            "s3.secret-access-key": MINIO_SECRET_KEY,
            "s3.region": MINIO_REGION,
            "s3.path-style-access": "true",
        },
    )


def get_s3_client():

    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name=MINIO_REGION,
    )


def sql_ident(name):

    return '"' + name.replace('"', '""') + '"'


def individua_colonna(table):

    columns = [
        field.name
        for field in table.schema().fields
    ]

    if SENSOR_COLUMN is not None:

        if SENSOR_COLUMN not in columns:
            raise RuntimeError(
                f"Colonna sensore non trovata: "
                f"{SENSOR_COLUMN}. "
                f"Colonne disponibili: {columns}"
            )

        return SENSOR_COLUMN

    for candidate in SENSOR_COLUMNS:

        if candidate in columns:
            return candidate

    raise RuntimeError(
        "Impossibile individuare la colonna sensore. "
        f"Colonne disponibili: {columns}. "
        "Impostare SENSOR_COLUMN manualmente."
    )


def individua_sensore(path, colonna):

    if SENSOR_VALUE is not None:
        return SENSOR_VALUE

    con = duck()

    try:

        col = sql_ident(colonna)

        sql = f"""
            SELECT {col}
            FROM {scan(path)}
            WHERE {col} IS NOT NULL
            GROUP BY {col}
            ORDER BY CAST({col} AS VARCHAR)
            LIMIT 1
        """

        row = con.execute(sql).fetchone()

        if row is None:
            raise RuntimeError(
                "Nessun sensore non nullo trovato."
            )

        return row[0]

    finally:
        con.close()


def conta_righe(path, colonna, sensore,
                snapshot_id=None):

    con = duck()

    try:

        col = sql_ident(colonna)

        source = scan(path, snapshot_id)

        sql = f"""
            SELECT COUNT(*)
            FROM {source}
            WHERE {col} = ?
        """

        return con.execute(
            sql,
            [sensore]
        ).fetchone()[0]

    finally:
        con.close()


def statistiche_iceberg(table):

    files = table.inspect.files().to_pylist()

    data_files = [
        f for f in files
        if int(f["content"]) == 0
    ]

    total_bytes = sum(
        int(f["file_size_in_bytes"])
        for f in data_files
    )

    return {
        "numero_file_attivi": len(data_files),
        "byte_file_attivi": total_bytes,
        "MiB_file_attivi": round(
            total_bytes / 1024**2, 3
        ),
    }


def statistiche_minio(client, table_location):

    parsed = urlparse(table_location)

    if parsed.scheme != "s3":
        raise RuntimeError(
            f"Location S3 non valida: {table_location}"
        )

    bucket = parsed.netloc
    prefix = parsed.path.lstrip("/").rstrip("/") + "/"

    paginator = client.get_paginator(
        "list_objects_v2"
    )

    numero_oggetti = 0
    byte_totali = 0

    for page in paginator.paginate(
        Bucket=bucket,
        Prefix=prefix
    ):

        for obj in page.get("Contents", []):

            numero_oggetti += 1
            byte_totali += obj["Size"]

    return {
        "bucket": bucket,
        "prefix": prefix,
        "numero_oggetti": numero_oggetti,
        "byte_fisici": byte_totali,
        "MiB_fisici": round(
            byte_totali / 1024**2, 3
        ),
    }


def esegui_dataset(catalog, client, tag, table_name):

    ident = f"{NAMESPACE}.{table_name}"

    print(f"\n{'=' * 60}")
    print(f"DATASET {tag}")
    print(f"Tabella: {ident}")
    print(f"{'=' * 60}")

    if not catalog.table_exists(ident):
        raise RuntimeError(
            f"Tabella Iceberg non trovata: {ident}"
        )

    table = catalog.load_table(ident)

    snapshot_prima = table.current_snapshot()

    if snapshot_prima is None:
        raise RuntimeError(
            f"{ident}: nessuno snapshot disponibile."
        )

    snapshot_id_prima = snapshot_prima.snapshot_id

    colonna = individua_colonna(table)

    path = metadata_path(tag)

    sensore = individua_sensore(
        path,
        colonna
    )

    print("\nSENSORE SELEZIONATO")
    print(f"Colonna: {colonna}")
    print(f"Valore: {sensore}")

    righe_prima = conta_righe(
        path,
        colonna,
        sensore
    )

    if righe_prima == 0:
        raise RuntimeError(
            f"Nessuna lettura presente per "
            f"il sensore {sensore}."
        )

    print("\nFASE 1 - STATO INIZIALE")

    iceberg_prima = statistiche_iceberg(table)

    minio_prima = statistiche_minio(
        client,
        table.location()
    )

    print(f"Snapshot: {snapshot_id_prima}")
    print(f"Letture sensore: {righe_prima}")

    print(
        f"File Iceberg attivi: "
        f"{iceberg_prima['numero_file_attivi']}"
    )

    print(
        f"Spazio file attivi: "
        f"{iceberg_prima['MiB_file_attivi']} MiB"
    )

    print(
        f"Spazio fisico MinIO: "
        f"{minio_prima['MiB_fisici']} MiB"
    )

    print("\nFASE 2 - CANCELLAZIONE")

    start_delete = time.perf_counter()

    table.delete(
        delete_filter=EqualTo(
            colonna,
            sensore
        ),
        snapshot_properties={
            "benchmark": "C4",
            "sensore_eliminato": str(sensore),
        },
    )

    tempo_delete = (
        time.perf_counter() - start_delete
    )

    print(
        f"Tempo cancellazione: "
        f"{tempo_delete:.6f} s"
    )

    print("\nFASE 3 - VERIFICA CANCELLAZIONE")

    table = catalog.load_table(ident)

    snapshot_dopo = table.current_snapshot()

    if snapshot_dopo is None:
        raise RuntimeError(
            "Snapshot corrente non disponibile."
        )

    snapshot_id_dopo = snapshot_dopo.snapshot_id

    if snapshot_id_prima == snapshot_id_dopo:
        raise RuntimeError(
            "La cancellazione non ha prodotto "
            "un nuovo snapshot."
        )

    path_dopo = metadata_path(tag)

    righe_dopo = conta_righe(
        path_dopo,
        colonna,
        sensore
    )

    cancellazione_verificata = (
        righe_dopo == 0
    )

    print(f"Snapshot nuovo: {snapshot_id_dopo}")
    print(f"Letture residue: {righe_dopo}")

    if not cancellazione_verificata:
        raise RuntimeError(
            "La cancellazione non è completa."
        )

    print("Cancellazione verificata.")

    print("\nFASE 4 - ANALISI SPAZIO")

    iceberg_dopo = statistiche_iceberg(table)

    minio_dopo = statistiche_minio(
        client,
        table.location()
    )

    variazione_byte_attivi = (
        iceberg_dopo["byte_file_attivi"]
        - iceberg_prima["byte_file_attivi"]
    )

    variazione_byte_fisici = (
        minio_dopo["byte_fisici"]
        - minio_prima["byte_fisici"]
    )

    spazio_attivo_ridotto = (
        -variazione_byte_attivi
    )

    spazio_fisico_liberato = (
        -variazione_byte_fisici
    )

    print(
        f"File attivi: "
        f"{iceberg_prima['numero_file_attivi']} -> "
        f"{iceberg_dopo['numero_file_attivi']}"
    )

    print(
        f"Variazione spazio attivo: "
        f"{variazione_byte_attivi / 1024**2:.3f} MiB"
    )

    print(
        f"Variazione spazio fisico MinIO: "
        f"{variazione_byte_fisici / 1024**2:.3f} MiB"
    )

    print("\nFASE 5 - TIME TRAVEL")

    start_travel = time.perf_counter()

    errore_travel = None

    try:

        righe_recuperate = conta_righe(
            path_dopo,
            colonna,
            sensore,
            snapshot_id=snapshot_id_prima
        )

        recuperabile = (
            righe_recuperate == righe_prima
        )

    except Exception as exc:

        righe_recuperate = None
        recuperabile = False
        errore_travel = str(exc)

    tempo_travel = (
        time.perf_counter() - start_travel
    )

    print(
        f"Snapshot precedente: "
        f"{snapshot_id_prima}"
    )

    print(
        f"Righe recuperate: {righe_recuperate}"
    )

    print(
        f"Time travel riuscito: {recuperabile}"
    )

    if errore_travel:
        print(f"Errore time travel: {errore_travel}")

    print(
        f"Tempo time travel: "
        f"{tempo_travel:.6f} s"
    )

    print("\nRISULTATO FINALE")

    print(f"Dataset: {tag}")
    print(f"Sensore: {sensore}")
    print(f"Righe cancellate: {righe_prima}")
    print(f"Tempo DELETE: {tempo_delete:.6f} s")

    print(
        f"Riduzione netta file attivi: "
        f"{spazio_attivo_ridotto / 1024**2:.3f} MiB"
    )

    print(
        f"Spazio fisico netto liberato: "
        f"{spazio_fisico_liberato / 1024**2:.3f} MiB"
    )

    print(
        f"Recuperabile con time travel: "
        f"{recuperabile}"
    )

    return {
        "tabella": ident,
        "colonna_sensore": colonna,
        "sensore": str(sensore),
        "righe_prima": righe_prima,
        "righe_dopo": righe_dopo,
        "righe_cancellate": righe_prima - righe_dopo,
        "tempo_delete_secondi": round(
            tempo_delete, 6
        ),
        "snapshot_prima": snapshot_id_prima,
        "snapshot_dopo": snapshot_id_dopo,
        "file_attivi_prima": (
            iceberg_prima["numero_file_attivi"]
        ),
        "file_attivi_dopo": (
            iceberg_dopo["numero_file_attivi"]
        ),
        "byte_attivi_prima": (
            iceberg_prima["byte_file_attivi"]
        ),
        "byte_attivi_dopo": (
            iceberg_dopo["byte_file_attivi"]
        ),
        "variazione_byte_attivi": (
            variazione_byte_attivi
        ),
        "byte_fisici_prima": (
            minio_prima["byte_fisici"]
        ),
        "byte_fisici_dopo": (
            minio_dopo["byte_fisici"]
        ),
        "variazione_byte_fisici": (
            variazione_byte_fisici
        ),
        "spazio_fisico_liberato_byte": (
            spazio_fisico_liberato
        ),
        "cancellazione_verificata": (
            cancellazione_verificata
        ),
        "righe_recuperate_time_travel": (
            righe_recuperate
        ),
        "time_travel_riuscito": recuperabile,
        "tempo_time_travel_secondi": round(
            tempo_travel, 6
        ),
        "errore_time_travel": errore_travel,
    }


def execute():

    catalog = get_catalog()
    client = get_s3_client()

    results = {}

    for tag, table_name in TABLES.items():

        results[tag] = esegui_dataset(
            catalog,
            client,
            tag,
            table_name
        )

    return results


if __name__ == "__main__":
    run("C4", execute)
