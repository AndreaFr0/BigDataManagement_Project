#!/usr/bin/env python3
"""Rimuove le registrazioni Iceberg indicate dal catalogo PostgreSQL e
cancella gli oggetti dal prefisso fisico MinIO del namespace.

Eseguire solo quando si vuole ricostruire il namespace da zero.
Usa le credenziali già configurate in common.py.
"""

from urllib.parse import quote, urlparse

import boto3
from botocore.config import Config
from pyiceberg.catalog.sql import SqlCatalog
from pyiceberg.exceptions import NoSuchNamespaceError, NoSuchTableError

from common import (
    BUCKET,
    CATALOG_NAME,
    PG_DB,
    PG_HOST,
    PG_PASSWORD,
    PG_PORT,
    PG_SCHEMA,
    PG_USER,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_ENDPOINT,
    MINIO_REGION,
)

# ==================== CONFIGURAZIONE ELIMINAZIONE ====================
NAMESPACE_DA_ELIMINARE = "benchmark"
PREFIX_BASE = ""
TABELLE_DA_ELIMINARE = ("letture_1m", "letture_10m")

# False: mostra cosa verrebbe cancellato, senza cambiare nulla.
ESEGUI_ELIMINAZIONE = True
CONFERMA_ELIMINAZIONE = "ELIMINA:warehouse/benchmark/"
# ===================================================================


def prefix_namespace():
    namespace = NAMESPACE_DA_ELIMINARE.strip().strip("/")
    base = PREFIX_BASE.strip().strip("/")
    if not namespace or namespace in (".", "..") or "/" in namespace:
        raise ValueError("NAMESPACE_DA_ELIMINARE deve essere un singolo nome valido")
    if any(part in (".", "..") for part in base.split("/")):
        raise ValueError("PREFIX_BASE non valido")
    return f"{base + '/' if base else ''}{namespace}/"


def client_minio():
    parsed = urlparse(MINIO_ENDPOINT)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("MINIO_ENDPOINT non valido")
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name=MINIO_REGION,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def get_catalog():
    user = quote(PG_USER, safe="")
    password = quote(PG_PASSWORD, safe="")
    uri = (
        f"postgresql+psycopg2://{user}:{password}@{PG_HOST}:{PG_PORT}/{PG_DB}"
        f"?options=-c%20search_path%3D{quote(PG_SCHEMA, safe='')}"
    )
    return SqlCatalog(CATALOG_NAME, uri=uri, warehouse=f"s3://{BUCKET}")


def main():
    prefix = prefix_namespace()
    if not BUCKET or "/" in BUCKET:
        raise ValueError("BUCKET non valido")

    expected = f"ELIMINA:{BUCKET}/{prefix}"
    if ESEGUI_ELIMINAZIONE and CONFERMA_ELIMINAZIONE != expected:
        raise RuntimeError(f"Conferma errata: usare {expected!r}")

    catalog = get_catalog()
    try:
        presenti = {".".join(item) for item in catalog.list_tables(NAMESPACE_DA_ELIMINARE)}
    except NoSuchNamespaceError:
        presenti = set()

    autorizzate = {f"{NAMESPACE_DA_ELIMINARE}.{name}" for name in TABELLE_DA_ELIMINARE}
    estranee = presenti - autorizzate
    print(f"Catalogo: {CATALOG_NAME}")
    print(f"Tabelle presenti: {sorted(presenti)}")
    print(f"Tabelle da eliminare: {sorted(presenti & autorizzate)}")
    print(f"Bucket: {BUCKET} | Prefisso: {prefix}")

    # Il prefisso MinIO comprende TUTTO il namespace: non cancellarlo
    # se altre tabelle risultano registrate in PostgreSQL.
    if estranee:
        raise RuntimeError(
            f"Operazione bloccata: nel namespace sono registrate altre tabelle: {sorted(estranee)}"
        )

    s3 = client_minio()
    paginator = s3.get_paginator("list_objects_v2")
    count = 0
    total_bytes = 0
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            count += 1
            total_bytes += obj.get("Size", 0)
            if not ESEGUI_ELIMINAZIONE and count <= 20:
                print(f"[ANTEPRIMA] {obj['Key']}")
    print(f"Oggetti trovati: {count}; byte: {total_bytes}")

    if not ESEGUI_ELIMINAZIONE:
        print("[ANTEPRIMA] Nessuna modifica eseguita.")
        return

    # Prima il catalogo, poi i file fisici. drop_table non carica
    # il metadata JSON: funziona anche quando il file è già mancante.
    for ident in sorted(autorizzate):
        try:
            catalog.drop_table(ident)
            print(f"[CATALOGO] Rimossa registrazione: {ident}")
        except NoSuchTableError:
            print(f"[CATALOGO] Già assente: {ident}")

    deleted = 0
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        objects = page.get("Contents", [])
        for start in range(0, len(objects), 1000):
            batch = objects[start:start + 1000]
            response = s3.delete_objects(
                Bucket=BUCKET,
                Delete={"Objects": [{"Key": obj["Key"]} for obj in batch], "Quiet": True},
            )
            if response.get("Errors"):
                raise RuntimeError(f"Eliminazione MinIO incompleta: {response['Errors']}")
            deleted += len(batch)
    print(f"[MINIO] Oggetti eliminati: {deleted}")
    print("[OK] Tabelle rimosse dal catalogo e prefisso MinIO ripulito.")
    print("Il namespace logico Iceberg è stato mantenuto.")


if __name__ == "__main__":
    main()
