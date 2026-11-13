"""
O4 - METADATI POPOLATI AUTOMATICAMENTE DA OPENMETADATA

Per ogni dataset:
1. Legge lo schema Iceberg tramite DuckDB
2. Conta le colonne presenti in Iceberg
3. Recupera i metadati della tabella da OpenMetadata
4. Conta i campi registrati in OpenMetadata
5. Confronta i conteggi
"""

import time
from urllib.parse import quote

import requests

from common import (
    run,
    duck,
    metadata_path,
    scan,
    TABLES,
    NAMESPACE,
    OPENMETADATA_URL,
    OPENMETADATA_TOKEN,
    OPENMETADATA_TABLES,
)


REQUEST_TIMEOUT = 30


def get_openmetadata_table(tag):

    fqn = OPENMETADATA_TABLES.get(tag)

    if not fqn:
        return {
            "stato": "NON_CONFIGURATO",
            "numero_campi": None,
            "nomi_campi": [],
            "tempo_secondi": None,
            "errore": (
                "Specificare il nome completo della tabella "
                "OpenMetadata in OPENMETADATA_TABLES."
            ),
        }

    url = (
        OPENMETADATA_URL.rstrip("/")
        + "/v1/tables/name/"
        + quote(fqn, safe="")
    )

    headers = {
        "Accept": "application/json"
    }

    # Il login nell'interfaccia web NON autentica automaticamente requests.
    # Il token va passato tramite variabile d'ambiente OPENMETADATA_TOKEN.
    token = OPENMETADATA_TOKEN.strip()
    if token:
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        headers["Authorization"] = f"Bearer {token}"

    start = time.perf_counter()

    try:

        response = requests.get(
            url,
            headers=headers,
            params={"fields": "columns"},
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 401:
            raise requests.HTTPError(
                "401 Unauthorized: token OpenMetadata mancante, scaduto "
                "o non valido. Genera un nuovo Access Token dal profilo "
                "OpenMetadata e imposta OPENMETADATA_TOKEN nell'ambiente "
                "prima di avviare O4.py.",
                response=response,
            )

        response.raise_for_status()

        data = response.json()

        columns = data.get("columns", [])

        tempo = time.perf_counter() - start

        return {
            "stato": "OK",
            "numero_campi": len(columns),
            "nomi_campi": [
                col["name"]
                for col in columns
            ],
            "tempo_secondi": round(tempo, 6),
            "errore": None,
        }

    except requests.RequestException as exc:

        return {
            "stato": "ERRORE",
            "numero_campi": None,
            "nomi_campi": [],
            "tempo_secondi": round(
                time.perf_counter() - start, 6
            ),
            "errore": str(exc),
        }


def get_iceberg_schema(con, tag):

    path = metadata_path(tag)

    sql = f"""
        DESCRIBE SELECT *
        FROM {scan(path)}
    """

    start = time.perf_counter()

    result = con.execute(sql).fetchall()

    tempo = time.perf_counter() - start

    columns = [
        row[0]
        for row in result
    ]

    return {
        "numero_campi": len(columns),
        "nomi_campi": columns,
        "tempo_secondi": round(tempo, 6),
    }


def execute():

    con = duck()

    try:

        out = {}

        for tag, table_name in TABLES.items():

            print(f"\n{'=' * 60}")
            print(f"DATASET {tag}")
            print(f"Tabella Iceberg: {NAMESPACE}.{table_name}")
            print(f"{'=' * 60}")

            iceberg = get_iceberg_schema(
                con,
                tag
            )

            openmetadata = get_openmetadata_table(
                tag
            )

            numero_iceberg = iceberg["numero_campi"]

            numero_openmetadata = (
                openmetadata["numero_campi"]
            )

            if numero_openmetadata is None:

                differenza = None
                corrispondenza = None

            else:

                differenza = (
                    numero_iceberg
                    - numero_openmetadata
                )

                corrispondenza = (
                    set(iceberg["nomi_campi"])
                    == set(openmetadata["nomi_campi"])
                )

            print("\nICEBERG")
            print(f"Numero campi: {numero_iceberg}")

            print("\nOPENMETADATA")
            print(
                f"Stato: {openmetadata['stato']}"
            )
            print(
                f"Numero campi: {numero_openmetadata}"
            )

            print("\nCONFRONTO")
            print(
                f"Differenza conteggio: {differenza}"
            )
            print(
                f"Stessi nomi dei campi: {corrispondenza}"
            )

            if openmetadata["errore"]:
                print(openmetadata["errore"])

            out[tag] = {
                "tabella_iceberg": (
                    f"{NAMESPACE}.{table_name}"
                ),
                "tabella_openmetadata": (
                    OPENMETADATA_TABLES.get(tag)
                ),
                "numero_campi_iceberg": (
                    numero_iceberg
                ),
                "numero_campi_openmetadata": (
                    numero_openmetadata
                ),
                "differenza_campi": differenza,
                "corrispondenza_campi": (
                    corrispondenza
                ),
                "stato_openmetadata": (
                    openmetadata["stato"]
                ),
                "tempo_iceberg_secondi": (
                    iceberg["tempo_secondi"]
                ),
                "tempo_openmetadata_secondi": (
                    openmetadata["tempo_secondi"]
                ),
                "campi_iceberg": ", ".join(
                    iceberg["nomi_campi"]
                ),
                "campi_openmetadata": ", ".join(
                    openmetadata["nomi_campi"]
                ),
                "errore_openmetadata": (
                    openmetadata["errore"]
                ),
            }

        return out

    finally:
        con.close()


if __name__ == "__main__":
    run("O4", execute)
