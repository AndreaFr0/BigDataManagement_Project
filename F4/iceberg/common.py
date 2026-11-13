"""Funzioni comuni per il benchmark Iceberg/DuckDB. """
import csv
import datetime
import decimal
import json
import statistics
import time
from pathlib import Path
from urllib.parse import urlparse

import duckdb
import psycopg2

# CONFIGURAZIONE
PG_HOST = 'localhost'
PG_PORT = 5432
PG_DB = 'progetto_db'
PG_USER = 'admin'
PG_PASSWORD = 'postgres'
PG_SCHEMA = 'iceberg_catalog'
CATALOG_NAME = 'default'
BUCKET = 'warehouse'
NAMESPACE = 'benchmark'
#TABLES = {'1M': 'sensori_1m'}
#TABLES = {'10M': 'sensori_10m'}
TABLES = {'1M': 'letture_1m', '10M': 'letture_10m'}
MINIO_FOLDERS = {
    "1M": "letture_1M",
    "10M": "letture_10M",
}

MINIO_ENDPOINT = 'http://localhost:9000'
MINIO_ACCESS_KEY = 'admin'
MINIO_SECRET_KEY = 'admin12345'
MINIO_REGION = 'us-east-1'

OPENMETADATA_URL = "http://localhost:8585/api"
OPENMETADATA_TOKEN = "eyJraWQiOiJHYjM4OWEtOWY3Ni1nZGpzLWE5MmotMDI0MmJrOTQzNTYiLCJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJvcGVuLW1ldGFkYXRhLm9yZyIsInN1YiI6ImFkbWluIiwicm9sZXMiOlsiQWRtaW4iXSwiZW1haWwiOiJhZG1pbkBvcGVuLW1ldGFkYXRhLm9yZyIsImlzQm90IjpmYWxzZSwidG9rZW5UeXBlIjoiUEVSU09OQUxfQUNDRVNTIiwidXNlcm5hbWUiOiJhZG1pbiIsInByZWZlcnJlZF91c2VybmFtZSI6ImFkbWluIiwiaWF0IjoxNzkzODg5MzYyLCJleHAiOjE4MDE2NjUzNjJ9.dRFNMPGjyJpAihm04TCYJ1LTlIKrmLnpYfm6KmvBl0ToZhTdcVxG9lD8GCa6f2VmbfA1l_XxYbxWDi-W4Yoyh6flrD3nfZuYCHGI_J5jxEQCg8q-kEBRDRKqvf_KlvYdjnUQU3fqXEJk1i9pqRAlXdb7ccPfKlrG_KDT8-JIiZFdjwU5PWNMUiDX6VlHzoZTFk0t77AmSYRLloJnjo-yVDAaTr4kYSOsSOJMFGGapxaWQH3TbNVE3lzn3lR7ibRCyBk8x9u3QS6Qz-LkrK8QvjNalgsfC-NmxCcD3VFDiF9j_5nASo5XKCxNu1LGs_lDIkAGIxuqT2_FyUVln5aDJg"
OPENMETADATA_TABLES = {
    "1M": "Iceberg local.default.benchmark.letture_1m",
    "10M": "Iceberg local.default.benchmark.letture_10m"
}

PREVIEW_ROWS = 5
RESULTS_DIR = Path(__file__).resolve().parent.parent / 'Results_Iceberg'
NUM_ESECUZIONI = 3  # Prima esecuzione + almeno due successive per la mediana.


def sql_ident(s):
    if not s or not s.replace('_', '').isalnum() or s[0].isdigit():
        raise ValueError('Identificatore SQL non valido: ' + s)
    return '"' + s + '"'


def lit(v):
    return "'" + str(v).replace("'", "''") + "'"


def db():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASSWORD,
    )


def metadata_path(tag):
    query = (
        f'SELECT metadata_location FROM {sql_ident(PG_SCHEMA)}.iceberg_tables '
        'WHERE catalog_name=%s AND table_namespace=%s AND table_name=%s'
    )
    with db() as pg:
        with pg.cursor() as cur:
            cur.execute(query, (CATALOG_NAME, NAMESPACE, TABLES[tag]))
            row = cur.fetchone()
    if not row:
        raise LookupError(
            f'Tabella Iceberg non trovata: {CATALOG_NAME}.{NAMESPACE}.{TABLES[tag]}'
        )
    return row[0]


def duck():
    con = duckdb.connect()
    con.execute('INSTALL httpfs; LOAD httpfs; INSTALL iceberg; LOAD iceberg;')
    endpoint = urlparse(MINIO_ENDPOINT)
    if not endpoint.netloc or endpoint.scheme not in ('http', 'https'):
        raise ValueError('MINIO_ENDPOINT deve essere http://host:porta o https://host:porta')
    con.execute(f'''CREATE OR REPLACE SECRET minio_secret (
        TYPE S3,
        KEY_ID {lit(MINIO_ACCESS_KEY)},
        SECRET {lit(MINIO_SECRET_KEY)},
        REGION {lit(MINIO_REGION)},
        ENDPOINT {lit(endpoint.netloc)},
        URL_STYLE 'path',
        USE_SSL {'true' if endpoint.scheme == 'https' else 'false'}
    )''')
    con.execute("SET TimeZone = 'UTC'")
    return con


def scan(path, snapshot_id=None):
    if snapshot_id is None:
        return f'iceberg_scan({lit(path)})'
    if not isinstance(snapshot_id, int) or snapshot_id <= 0:
        raise ValueError('Snapshot ID numerico positivo obbligatorio')
    return f'iceberg_scan({lit(path)}, snapshot_from_id = {snapshot_id})'


def safe(value):
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, bytes):
        return '<binary>'
    if isinstance(value, (list, dict)):
        return json.loads(json.dumps(value, default=str, ensure_ascii=False))
    return value


def _csv_value(value):
    value = safe(value)
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return value


def _tag_from_name(name):
    if name:
        for tag in TABLES:
            if name == tag or name.endswith('_' + tag):
                return tag
    return ''


def timed_query(con, sql, params=None, *, name=None, preview=PREVIEW_ROWS):
    started = time.perf_counter()
    cur = con.execute(sql, [] if params is None else params)
    rows = cur.fetchall()
    seconds = time.perf_counter() - started
    columns = [col[0] for col in cur.description]

    return {
        'tempo_secondi': round(seconds, 6),
        'righe_risultato': len(rows),
        'anteprima': [
            dict(zip(columns, (safe(v) for v in row)))
            for row in rows[:preview]
        ],
    }


def for_each(test_id, sql_factory, tags=None):
    # Se tags non è specificato, usa le tabelle attualmente abilitate in TABLES.
    if tags is None:
        tags = tuple(TABLES)
    con = duck()
    try:
        results = {}
        for tag in tags:
            path = metadata_path(tag)
            sql, params = sql_factory(scan(path), tag)
            results[tag] = {
                'tabella': f'{NAMESPACE}.{TABLES[tag]}',
                'metadata_location': path,
                **timed_query(con, sql, params, name=f'{test_id}_{tag}'),
            }
        return results
    finally:
        con.close()


def not_executed(reason, *, next_step=None):
    out = {'stato': 'NON_ESEGUITA', 'tempo_secondi': None, 'motivo': reason}
    if next_step:
        out['azione_necessaria'] = next_step
    return out


def _write_csv(test_id, times_by_tag):
    """Un CSV per prova, con tempi distinti per ciascuna taglia elaborata."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    destination = RESULTS_DIR / f'{test_id}.csv'

    with destination.open('w', newline='', encoding='utf-8-sig') as fh:
        writer = csv.DictWriter(
            fh, fieldnames=['dataset', 'misura', 'tempo_totale_secondi']
        )
        writer.writeheader()
        for tag, times in times_by_tag.items():
            writer.writerow({
                'dataset': tag,
                'misura': 'prima_esecuzione',
                'tempo_totale_secondi': round(times[0], 6),
            })
            writer.writerow({
                'dataset': tag,
                'misura': 'mediana_esecuzioni_successive',
                'tempo_totale_secondi': round(statistics.median(times[1:]), 6),
            })
    return destination


def run(test_id, fn):
    if not isinstance(NUM_ESECUZIONI, int) or NUM_ESECUZIONI < 3:
        raise ValueError('NUM_ESECUZIONI deve essere un intero maggiore o uguale a 3')

    # Congela le taglie configurate. TABLES viene modificato IN PLACE,
    # così anche gli script che importano TABLES con "from common import TABLES"
    # vedono soltanto il dataset attualmente misurato.
    configured_tables = dict(TABLES)
    times_by_tag = {}
    active_tag = None

    try:
        for tag, table_name in configured_tables.items():
            active_tag = tag
            TABLES.clear()
            TABLES[tag] = table_name

            times = []
            times_by_tag[tag] = times
            for _ in range(NUM_ESECUZIONI):
                started = time.perf_counter()
                fn()
                times.append(time.perf_counter() - started)

        path = _write_csv(test_id, times_by_tag)
        print(json.dumps({
            'prova': test_id,
            'numero_esecuzioni_per_dataset': NUM_ESECUZIONI,
            'tempi_per_dataset': {
                tag: {
                    'prima_esecuzione_secondi': round(times[0], 6),
                    'mediana_esecuzioni_successive_secondi': round(
                        statistics.median(times[1:]), 6
                    ),
                }
                for tag, times in times_by_tag.items()
            },
            'file_csv': str(path),
        }, indent=2, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({
            'prova': test_id,
            'dataset': active_tag,
            'esecuzioni_completate': len(times_by_tag.get(active_tag, [])),
            'errore': str(exc),
            'tipo_errore': type(exc).__name__,
        }, indent=2, ensure_ascii=False))
        raise
    finally:
        TABLES.clear()
        TABLES.update(configured_tables)
