#!/usr/bin/env python3
"""
A3.6 - Collegamento snapshot Iceberg -> scheda Dataverse.

Legge i metadati dello snapshot corrente di una tabella Iceberg (PyIceberg),
estrae un mese di dati, compila la scheda Dataverse e la pubblica via API
(crea dataset, carica file, pubblica).

Dipendenze:
    pip install "pyiceberg[sql-postgres,s3fs]" pyarrow pandas requests

Variabili d'ambiente (nessuna credenziale e' scritta nello script):
    MY_TOKEN            token API Dataverse (obbligatorio)
    CATALOG_URI         default postgresql+psycopg2://admin:postgres@localhost:5432/progetto_db?options=-csearch_path%3Diceberg_catalog
    MINIO_ENDPOINT      default http://localhost:9000
    MINIO_ACCESS_KEY    default admin
    MINIO_SECRET_KEY    obbligatorio
    WAREHOUSE           default s3://warehouse/
    TABELLA             default iot.letture_1m
    DATAVERSE_ALIAS     default testBDMProject
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd
import requests
from pyiceberg.catalog import load_catalog

# --- Configurazione ---------------------------------------------------------
CATALOG_URI = os.environ.get(
    "CATALOG_URI",
    "postgresql+psycopg2://admin:postgres@localhost:5432/progetto_db"
    "?options=-csearch_path%3Diceberg_catalog",
)
CATALOG_NAME = os.environ.get("CATALOG_NAME", "default")
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "admin12345")
WAREHOUSE = os.environ.get("WAREHOUSE", "s3://warehouse/")
TABELLA = os.environ.get("TABELLA", "iot.letture_1m")
DATAVERSE_URL = "https://demo.dataverse.org"
DATAVERSE_ALIAS = os.environ.get("DATAVERSE_ALIAS", "progettoDBM")
TOKEN = os.environ.get("MY_TOKEN", "cef0e767-c2b4-419e-ab44-6c0763fc6db9")

# Estratto: un solo mese
INIZIO = "2024-01-01T00:00:00+00:00"
FINE = "2024-02-01T00:00:00+00:00"
FILE_ESTRATTO = "estratto_gennaio_2024.csv"

HEADERS = {"X-Dataverse-key": TOKEN}

# Autori del dataset (formato Dataverse: "Cognome, Nome"). Il primo e' l'autore
# principale; gli altri compaiono come co-autori nella citazione.
AFFILIAZIONE = "Universita del Salento"
AUTORI = [
    "Nocera, Davide",
    "Schito, Mattia Antonio",  # mattiaantonio.schito@studenti.unisalento.it
    "Franza, Andrea",          # andrea.franza@studenti.unisalento.it
]

# Account Dataverse dei co-autori (username senza "@"). Oltre a comparire come
# autori, ricevono un ruolo sul dataset. "curator" = possono modificare i
# metadati, caricare file e pubblicare. Alternative: "contributor" (modifica ma
# non pubblica), "admin" (controllo completo, compresi i permessi).
UTENTI_COAUTORI = ["MattiaS", "Andrea_Franza"]
RUOLO_COAUTORI = "curator"


# --- 1. Lettura snapshot Iceberg --------------------------------------------
def leggi_snapshot_ed_estratto():
    catalog = load_catalog(
        CATALOG_NAME,
        **{
            "type": "sql",
            "uri": CATALOG_URI,
            "warehouse": WAREHOUSE,
            "s3.endpoint": MINIO_ENDPOINT,
            "s3.access-key-id": MINIO_ACCESS_KEY,
            "s3.secret-access-key": MINIO_SECRET_KEY,
            "s3.path-style-access": "true",
        },
    )
    tabella = catalog.load_table(TABELLA)
    snap = tabella.current_snapshot()
    if snap is None:
        sys.exit("La tabella Iceberg non ha snapshot (e' vuota?).")

    summary = snap.summary or {}
    info = {
        "snapshot_id": snap.snapshot_id,
        "snapshot_ts": datetime.fromtimestamp(
            snap.timestamp_ms / 1000, tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "record_totali": summary.get("total-records", "n/d"),
    }

    df = tabella.scan(
        row_filter=f"ts >= '{INIZIO}' AND ts < '{FINE}'"
    ).to_pandas()
    if df.empty:
        sys.exit("L'estratto e' vuoto: controllare il filtro temporale.")

    df = df.sort_values("ts")
    df.to_csv(FILE_ESTRATTO, index=False)

    info["record_estratto"] = len(df)
    info["ts_min"] = pd.to_datetime(df["ts"]).min().strftime("%Y-%m-%d")
    info["ts_max"] = pd.to_datetime(df["ts"]).max().strftime("%Y-%m-%d")
    return info


# --- 2. Costruzione della scheda Dataverse ----------------------------------
def campo(nome, valore, tipo="primitive", multiplo=False):
    return {
        "typeName": nome,
        "value": valore,
        "typeClass": tipo,
        "multiple": multiplo,
    }


def costruisci_scheda(info):
    descrizione = (
        "Estratto di letture sintetiche di sensori ambientali urbani, "
        "generato nell'ambito del progetto Big Data Management "
        "(UniSalento). Dati prodotti con seme fisso. "
        f"Origine: tabella Iceberg {TABELLA}, snapshot {info['snapshot_id']} "
        f"({info['snapshot_ts']}). "
        f"Record nello snapshot: {info['record_totali']}; "
        f"record nell'estratto: {info['record_estratto']}. "
        f"Intervallo temporale: {info['ts_min']} - {info['ts_max']}."
    )
    return {
        "datasetVersion": {
            "license": {
                "name": "CC0 1.0",
                "uri": "http://creativecommons.org/publicdomain/zero/1.0",
            },
            "metadataBlocks": {
                "citation": {
                    "displayName": "Citation Metadata",
                    "fields": [
                        campo("title", "Letture sintetiche sensori urbani - gennaio 2024"),
                        campo(
                            "author",
                            [
                                {
                                    "authorName": campo("authorName", nome),
                                    "authorAffiliation": campo(
                                        "authorAffiliation", AFFILIAZIONE
                                    ),
                                }
                                for nome in AUTORI
                            ],
                            "compound", True,
                        ),
                        campo(
                            "datasetContact",
                            [{
                                "datasetContactName": campo("datasetContactName", "Nocera, Davide"),
                                "datasetContactEmail": campo(
                                    "datasetContactEmail",
                                    "davide.nocera1@studenti.unisalento.it",
                                ),
                            }],
                            "compound", True,
                        ),
                        campo(
                            "dsDescription",
                            [{"dsDescriptionValue": campo("dsDescriptionValue", descrizione)}],
                            "compound", True,
                        ),
                        campo("subject", ["Computer and Information Science"],
                              "controlledVocabulary", True),
                        campo(
                            "timePeriodCovered",
                            [{
                                "timePeriodCoveredStart": campo("timePeriodCoveredStart", info["ts_min"]),
                                "timePeriodCoveredEnd": campo("timePeriodCoveredEnd", info["ts_max"]),
                            }],
                            "compound", True,
                        ),
                    ],
                }
            },
        }
    }


# --- 3. Chiamate API Dataverse ----------------------------------------------
def crea_dataset(scheda):
    r = requests.post(
        f"{DATAVERSE_URL}/api/dataverses/{DATAVERSE_ALIAS}/datasets",
        headers={**HEADERS, "Content-Type": "application/json"},
        data=json.dumps(scheda),
    )
    print("Creazione dataset:", r.status_code, r.text)
    r.raise_for_status()
    return r.json()["data"]["persistentId"]


def assegna_ruoli(doi):
    """Assegna ai co-autori un ruolo sul dataset. Un errore qui non deve far
    perdere il dataset gia' creato: si segnala e si prosegue."""
    for utente in UTENTI_COAUTORI:
        r = requests.post(
            f"{DATAVERSE_URL}/api/datasets/:persistentId/assignments",
            params={"persistentId": doi},
            headers={**HEADERS, "Content-Type": "application/json"},
            data=json.dumps({"assignee": f"@{utente}", "role": RUOLO_COAUTORI}),
        )
        print(f"Ruolo '{RUOLO_COAUTORI}' a @{utente}:", r.status_code, r.text[:200])
        if not r.ok:
            print(f"ATTENZIONE: assegnazione fallita per @{utente} "
                  "(verificare lo username e che l'account esista su demo.dataverse.org).")


def carica_file(doi):
    with open(FILE_ESTRATTO, "rb") as f:
        r = requests.post(
            f"{DATAVERSE_URL}/api/datasets/:persistentId/add",
            params={"persistentId": doi},
            headers=HEADERS,
            files={"file": f},
        )
    print("Upload file:", r.status_code, r.text[:200])
    r.raise_for_status()


def attendi_sblocco(doi, timeout=180):
    """Dopo l'upload di un CSV, Dataverse blocca il dataset (ingest)."""
    for _ in range(timeout // 3):
        r = requests.get(
            f"{DATAVERSE_URL}/api/datasets/:persistentId/locks",
            params={"persistentId": doi},
            headers=HEADERS,
        )
        r.raise_for_status()
        if not r.json().get("data"):
            return
        print("Dataset bloccato (ingest in corso), attendo...")
        time.sleep(3)
    sys.exit("Timeout: il dataset e' ancora bloccato. Riprovare a pubblicare piu' tardi.")


def pubblica(doi):
    r = requests.post(
        f"{DATAVERSE_URL}/api/datasets/:persistentId/actions/:publish",
        params={"persistentId": doi, "type": "major"},
        headers=HEADERS,
    )
    print("Pubblicazione:", r.status_code, r.text[:200])
    r.raise_for_status()


def main():
    info = leggi_snapshot_ed_estratto()
    print("Metadati snapshot:", json.dumps(info, indent=2))

    doi = crea_dataset(costruisci_scheda(info))
    assegna_ruoli(doi)
    carica_file(doi)
    attendi_sblocco(doi)
    pubblica(doi)

    versione = requests.get(f"{DATAVERSE_URL}/api/info/version").json()
    print("\nDOI:", doi)
    print("Versione Dataverse:", versione.get("data", versione))


if __name__ == "__main__":
    main()
