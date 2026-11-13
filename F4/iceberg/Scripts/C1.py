'''
C1 - BENCHMARK DI SCRITTURA FRAMMENTATA ICEBERG

Per ogni dataset:
1. Misura prestazioni e numero di file iniziali
2. Esegue 100 append separati da 10.000 righe
3. Misura degrado e incremento dei file
4. Esegue compaction tramite overwrite Iceberg
5. Misura nuovamente le prestazioni

ATTENZIONE:
- Modifica le tabelle del namespace configurato in common.py
'''

import time

from pyiceberg.catalog.sql import SqlCatalog

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

BATCH_SIZE = 10000
REPETITIONS = 100
MONTHS = 6
ONLY_VALID = False


def get_catalog():

    uri = (
        f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}"
        f"@{PG_HOST}:{PG_PORT}/{PG_DB}"
        f"?options=-c%20search_path%3D{PG_SCHEMA}"
    )

    return SqlCatalog(
        CATALOG_NAME,
        uri=uri,
        warehouse="s3://lakehouse",
        **{
            "s3.endpoint": MINIO_ENDPOINT,
            "s3.access-key-id": MINIO_ACCESS_KEY,
            "s3.secret-access-key": MINIO_SECRET_KEY,
            "s3.region": MINIO_REGION,
            "s3.path-style-access": "true",
        },
    )


def statistiche(table):

    files = table.inspect.files().to_pylist()

    data_files = [
        f for f in files
        if int(f["content"]) == 0
    ]

    return {
        "numero_file": len(data_files),
        "numero_righe": sum(
            int(f["record_count"])
            for f in data_files
        ),
        "dimensione_bytes": sum(
            int(f["file_size_in_bytes"])
            for f in data_files
        ),
        "dimensione_MiB": round(
            sum(
                int(f["file_size_in_bytes"])
                for f in data_files
            ) / 1024**2,
            3,
        ),
    }


def misura_b1(tag):

    path = metadata_path(tag)

    valid_filter = (
        " AND d.qualita = 1"
        if ONLY_VALID else ""
    )

    sql = f"""
        WITH reference AS (
            SELECT MAX(ts) AS t_max
            FROM {scan(path)}
        )
        SELECT
            date_trunc('hour', d.ts) AS ora_utc,
            AVG(d.valore) AS media_idrometrica,
            COUNT(d.valore) AS letture_valide_numericamente
        FROM {scan(path)} d
        CROSS JOIN reference r
        WHERE d.tipo = 'idrometrico'
          AND d.ts > r.t_max - INTERVAL '{MONTHS} months'
          AND d.ts <= r.t_max
          {valid_filter}
        GROUP BY 1
        ORDER BY 1
    """

    con = duck()

    try:
        start = time.perf_counter()

        cur = con.execute(sql)
        rows = cur.fetchall()

        elapsed = time.perf_counter() - start

        return {
            "tempo_secondi": round(elapsed, 6),
            "righe_risultato": len(rows),
        }

    finally:
        con.close()


def variazione_percentuale(prima, dopo):

    if prima == 0:
        return None

    return round(
        ((dopo - prima) / prima) * 100,
        3,
    )


def esegui_dataset(catalog, tag, table_name):

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

    if table.spec().fields:
        raise RuntimeError(
            f"{ident}: la compaction prevista richiede "
            "una tabella non partizionata."
        )

    snapshot = table.current_snapshot()

    if snapshot is None:
        raise RuntimeError(
            f"{ident}: nessuno snapshot disponibile."
        )

    files = table.inspect.files().to_pylist()

    if any(int(f["content"]) != 0 for f in files):
        raise RuntimeError(
            f"{ident}: presenti delete file."
        )

    print("\nFASE 1 - STATO INIZIALE")

    prima = statistiche(table)
    b1_prima = misura_b1(tag)

    print(f"File iniziali: {prima['numero_file']}")
    print(f"Righe iniziali: {prima['numero_righe']}")
    print(f"Dimensione: {prima['dimensione_MiB']} MiB")
    print(f"Tempo B1: {b1_prima['tempo_secondi']} s")

    print("\nFASE 2 - SCRITTURA FRAMMENTATA")
    
    print("\nScrittura frammentata in corso...")
    
    dati_batch = table.scan(
        limit=BATCH_SIZE
    ).to_arrow()

    if dati_batch.num_rows != BATCH_SIZE:
        raise RuntimeError(
            f"{ident}: disponibili soltanto "
            f"{dati_batch.num_rows} righe."
        )

    start_append = time.perf_counter()

    for i in range(REPETITIONS):

        table.append(
            dati_batch,
            snapshot_properties={
                "benchmark": "C1",
                "batch": str(i + 1),
            },
        )


    tempo_append = time.perf_counter() - start_append

    table = catalog.load_table(ident)

    dopo_append = statistiche(table)

    righe_aggiunte = (
        dopo_append["numero_righe"]
        - prima["numero_righe"]
    )

    righe_attese = BATCH_SIZE * REPETITIONS

    if righe_aggiunte != righe_attese:
        raise RuntimeError(
            f"{ident}: righe aggiunte {righe_aggiunte}, "
            f"attese {righe_attese}."
        )

    print("\nFASE 3 - MISURAZIONE DOPO FRAMMENTAZIONE")

    b1_dopo_append = misura_b1(tag)

    degrado = variazione_percentuale(
        b1_prima["tempo_secondi"],
        b1_dopo_append["tempo_secondi"],
    )

    print(f"Righe aggiunte: {righe_aggiunte}")
    print(f"File attivi: {dopo_append['numero_file']}")
    print(f"Tempo append: {tempo_append:.6f} s")
    print(f"Tempo B1: {b1_dopo_append['tempo_secondi']} s")
    print(f"Degrado B1: {degrado}%")

    print("\nFASE 4 - COMPACTION ICEBERG")

    table = catalog.load_table(ident)

    start_compaction = time.perf_counter()

    dati_completi = table.scan().to_arrow()

    if dati_completi.num_rows != dopo_append["numero_righe"]:
        raise RuntimeError(
            f"{ident}: conteggio righe non coerente."
        )

    table.overwrite(
        dati_completi,
        snapshot_properties={
            "benchmark": "C1",
            "compaction": "true",
            "compaction.type": "full-rewrite",
        },
    )

    tempo_compaction = (
        time.perf_counter() - start_compaction
    )

    print(
        f"Tempo compaction: {tempo_compaction:.6f} s"
    )

    print("\nFASE 5 - MISURAZIONE FINALE")

    table = catalog.load_table(ident)

    dopo_compaction = statistiche(table)

    if (
        dopo_compaction["numero_righe"]
        != dopo_append["numero_righe"]
    ):
        raise RuntimeError(
            f"{ident}: la compaction ha modificato "
            "il numero di righe."
        )

    b1_dopo_compaction = misura_b1(tag)

    miglioramento = variazione_percentuale(
        b1_dopo_append["tempo_secondi"],
        b1_dopo_compaction["tempo_secondi"],
    )

    incremento_file = (
        dopo_append["numero_file"]
        - prima["numero_file"]
    )

    riduzione_file = (
        dopo_append["numero_file"]
        - dopo_compaction["numero_file"]
    )

    print("\nRISULTATO FINALE")

    print(
        f"File: {prima['numero_file']} -> "
        f"{dopo_append['numero_file']} -> "
        f"{dopo_compaction['numero_file']}"
    )

    print(
        f"Tempo B1: {b1_prima['tempo_secondi']} -> "
        f"{b1_dopo_append['tempo_secondi']} -> "
        f"{b1_dopo_compaction['tempo_secondi']} s"
    )

    print(
        f"Variazione dopo frammentazione: {degrado}%"
    )

    print(
        f"Variazione dopo compaction: {miglioramento}%"
    )

    return {
        "tabella": ident,
        "batch_size": BATCH_SIZE,
        "ripetizioni": REPETITIONS,
        "righe_aggiunte": righe_aggiunte,
        "prima": {
            **prima,
            "B1": b1_prima,
        },
        "dopo_frammentazione": {
            **dopo_append,
            "B1": b1_dopo_append,
        },
        "dopo_compaction": {
            **dopo_compaction,
            "B1": b1_dopo_compaction,
        },
        "incremento_file": incremento_file,
        "riduzione_file": riduzione_file,
        "degrado_B1_percento": degrado,
        "variazione_post_compaction_percento": miglioramento,
        "tempo_append_secondi": round(
            tempo_append, 6
        ),
        "tempo_compaction_secondi": round(
            tempo_compaction, 6
        ),
    }


def execute():

    catalog = get_catalog()

    results = {}

    for tag, table_name in TABLES.items():

        results[tag] = esegui_dataset(
            catalog,
            tag,
            table_name,
        )

    return results


if __name__ == "__main__":
    run("C1", execute)
