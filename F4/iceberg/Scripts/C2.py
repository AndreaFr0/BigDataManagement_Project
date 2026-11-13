'''
C2 - BENCHMARK DI EVOLUZIONE DELLO SCHEMA ICEBERG

Per ogni dataset:
1. Misura lo stato iniziale
2. Aggiunge un campo temporaneo di tipo string
3. Rinomina il campo appena aggiunto
4. Elimina il campo rinominato
5. Misura il tempo di ciascuna operazione
6. Verifica che i dati esistenti rimangano invariati

ATTENZIONE:
- Modifica lo schema delle tabelle del namespace configurato in common.py
'''

import time
from urllib.parse import quote

from pyiceberg.catalog.sql import SqlCatalog
from pyiceberg.types import StringType

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
)

COLONNA_NUOVA = "campo_test_c2"
COLONNA_RINOMINATA = "campo_test_c2_rinominato"


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
        warehouse="s3://lakehouse",
        **{
            "s3.endpoint": MINIO_ENDPOINT,
            "s3.access-key-id": MINIO_ACCESS_KEY,
            "s3.secret-access-key": MINIO_SECRET_KEY,
            "s3.region": MINIO_REGION,
            "s3.path-style-access": "true",
        },
    )


def nomi_colonne(table):

    return [
        field.name
        for field in table.schema().fields
    ]


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
    }


def verifica_dati(prima, dopo):

    if prima != dopo:
        raise RuntimeError(
            "I file o i conteggi dei dati sono cambiati."
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

    colonne_iniziali = nomi_colonne(table)

    if (
        COLONNA_NUOVA in colonne_iniziali
        or COLONNA_RINOMINATA in colonne_iniziali
    ):
        raise RuntimeError(
            f"{ident}: una colonna temporanea esiste gia'. "
            "Verificare lo schema prima di ripetere C2."
        )

    prima = statistiche(table)
    schema_id_iniziale = table.metadata.current_schema_id

    print("\nSTATO INIZIALE")
    print(f"Righe: {prima['numero_righe']}")
    print(f"File: {prima['numero_file']}")
    print(f"Schema ID: {schema_id_iniziale}")

    print("\nOPERAZIONE 1 - AGGIUNTA CAMPO")

    start = time.perf_counter()

    with table.update_schema() as update:
        update.add_column(
            COLONNA_NUOVA,
            StringType(),
            required=False,
        )

    tempo_add = time.perf_counter() - start

    table = catalog.load_table(ident)

    if COLONNA_NUOVA not in nomi_colonne(table):
        raise RuntimeError(
            "Il campo temporaneo non è stato aggiunto."
        )

    field_id_add = table.schema().find_field(
        COLONNA_NUOVA
    ).field_id

    dopo_add = statistiche(table)
    verifica_dati(prima, dopo_add)

    print(f"Campo aggiunto: {COLONNA_NUOVA}")
    print("Tipo: string")
    print(f"Field ID: {field_id_add}")
    print(f"Tempo ADD: {tempo_add:.6f} s")

    print("\nOPERAZIONE 2 - RINOMINA CAMPO")

    start = time.perf_counter()

    with table.update_schema() as update:
        update.rename_column(
            COLONNA_NUOVA,
            COLONNA_RINOMINATA,
        )

    tempo_rename = time.perf_counter() - start

    table = catalog.load_table(ident)

    colonne = nomi_colonne(table)

    if (
        COLONNA_NUOVA in colonne
        or COLONNA_RINOMINATA not in colonne
    ):
        raise RuntimeError(
            "La rinomina del campo non è riuscita."
        )

    field_id_rename = table.schema().find_field(
        COLONNA_RINOMINATA
    ).field_id

    if field_id_add != field_id_rename:
        raise RuntimeError(
            "Il Field ID è cambiato durante la rinomina."
        )

    dopo_rename = statistiche(table)
    verifica_dati(prima, dopo_rename)

    print(f"Nuovo nome: {COLONNA_RINOMINATA}")
    print(f"Field ID invariato: {field_id_rename}")
    print(f"Tempo RENAME: {tempo_rename:.6f} s")

    print("\nOPERAZIONE 3 - RIMOZIONE CAMPO")

    start = time.perf_counter()

    with table.update_schema(
        allow_incompatible_changes=True
    ) as update:
        update.delete_column(
            COLONNA_RINOMINATA
        )

    tempo_drop = time.perf_counter() - start

    table = catalog.load_table(ident)

    colonne_finali = nomi_colonne(table)

    if COLONNA_RINOMINATA in colonne_finali:
        raise RuntimeError(
            "Il campo temporaneo non è stato eliminato."
        )

    dopo_drop = statistiche(table)
    verifica_dati(prima, dopo_drop)

    if colonne_finali != colonne_iniziali:
        raise RuntimeError(
            "Lo schema finale è diverso da quello iniziale."
        )

    schema_id_finale = table.metadata.current_schema_id

    tempo_totale = (
        tempo_add
        + tempo_rename
        + tempo_drop
    )

    print(f"Campo eliminato: {COLONNA_RINOMINATA}")
    print(f"Tempo DROP: {tempo_drop:.6f} s")

    print("\nRISULTATO FINALE")

    print(f"ADD: {tempo_add:.6f} s")
    print(f"RENAME: {tempo_rename:.6f} s")
    print(f"DROP: {tempo_drop:.6f} s")
    print(f"TOTALE: {tempo_totale:.6f} s")

    print(
        f"Righe: {prima['numero_righe']} "
        f"-> {dopo_drop['numero_righe']}"
    )

    print(
        f"File: {prima['numero_file']} "
        f"-> {dopo_drop['numero_file']}"
    )

    print(
        f"Schema ID: {schema_id_iniziale} "
        f"-> {schema_id_finale}"
    )

    return {
        "tabella": ident,
        "tipo_campo": "string",
        "campo_aggiunto": COLONNA_NUOVA,
        "campo_rinominato": COLONNA_RINOMINATA,
        "tempo_add_secondi": round(tempo_add, 6),
        "tempo_rename_secondi": round(tempo_rename, 6),
        "tempo_drop_secondi": round(tempo_drop, 6),
        "tempo_totale_secondi": round(tempo_totale, 6),
        "righe_iniziali": prima["numero_righe"],
        "righe_finali": dopo_drop["numero_righe"],
        "file_iniziali": prima["numero_file"],
        "file_finali": dopo_drop["numero_file"],
        "schema_id_iniziale": schema_id_iniziale,
        "schema_id_finale": schema_id_finale,
        "field_id_invariato_rinomina": (
            field_id_add == field_id_rename
        ),
        "schema_ripristinato": (
            colonne_finali == colonne_iniziali
        ),
        "dati_invariati": (
            prima == dopo_drop
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
    run("C2", execute)
