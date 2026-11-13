"""Funzioni comuni per il benchmark Iceberg/DuckDB.

Ogni chiamata a run(test_id, fn) crea/sovrascrive:
- Performance_Results_Iceberg/<test_id>.csv: tempi della prima esecuzione e
  mediana dei tempi delle esecuzioni successive, per dataset.
- Query_Results_Iceberg/<test_id>.csv: se la prova produce un solo risultato.
- Query_Results_Iceberg/<test_id>_01.csv, _02.csv, ...: se la prova
  produce piu' risultati tramite timed_query().
I risultati di timed_query() hanno precedenza sul riepilogo di execute():
non vengono piu' creati due tipi di CSV per la stessa prova.

Per evitare duplicati nei risultati, viene esportata soltanto la prima delle
NUM_ESECUZIONI esecuzioni di ogni dataset. Se fn() esegue più query tramite
 timed_query(), ogni posizione della sequenza di query ha il proprio CSV,
con righe di entrambi i dataset quando presenti.
"""
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
# TABLES = {'1M': 'letture_1m'}
# TABLES = {'10M': 'letture_10m'}
TABLES = {'1M': 'letture_1m', '10M': 'letture_10m'}
MINIO_FOLDERS = {
    '1M': 'letture_1M',
    '10M': 'letture_10M',
}

MINIO_ENDPOINT = 'http://localhost:9000'
MINIO_ACCESS_KEY = 'admin'
MINIO_SECRET_KEY = 'admin12345'
MINIO_REGION = 'us-east-1'

OPENMETADATA_URL = 'http://localhost:8585/api'
# Il token, se necessario per altre prove, va caricato da variabile d'ambiente.
# Non inserire token di accesso personali direttamente nel sorgente.
import os
OPENMETADATA_TOKEN = "eyJraWQiOiJHYjM4OWEtOWY3Ni1nZGpzLWE5MmotMDI0MmJrOTQzNTYiLCJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJvcGVuLW1ldGFkYXRhLm9yZyIsInN1YiI6ImFkbWluIiwicm9sZXMiOlsiQWRtaW4iXSwiZW1haWwiOiJhZG1pbkBvcGVuLW1ldGFkYXRhLm9yZyIsImlzQm90IjpmYWxzZSwidG9rZW5UeXBlIjoiUEVSU09OQUxfQUNDRVNTIiwidXNlcm5hbWUiOiJhZG1pbiIsInByZWZlcnJlZF91c2VybmFtZSI6ImFkbWluIiwiaWF0IjoxNzk0Mzg0NjYyLCJleHAiOjE4MDIxNjA2NjJ9.modIgY-oR8TIsucxIRs_9baom_wYfPKPrkpoHduDNhYPtR7dYBvGCxOgoytip06TVreqXn__LB3Nqa2K9UHocoSUsPBZFONmiJ5V07L9AeDcbsNqeRdyLvqZXRWuIfcCbnHfOY5KsfOYD3-6_CYCwUXBkjdOEaobC3HuguRTieFGL6DbS-j9yiUqpujZgdGUr7adX5EqDQM3urVUKrEcj5Br-MyNpoCpmi8MKcDwcJc0onkPmurhl-zgIGrVwVRBnsVXSjjnoGXV8gduXyVPonuBY4Gcf9EGHYs7gq_KCtjlJ5QQK9ibT-vEL-bvNRBWS-Yyi9HKRCvhdy6IHfxasg"
OPENMETADATA_TABLES = {
    '1M': 'iceberg.default.benchmark.letture_1m',
    '10M': 'iceberg.default.benchmark.letture_10m',
}

PREVIEW_ROWS = 5
BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / 'Performance_Results_Iceberg'
QUERY_RESULTS_DIR = BASE_DIR / 'Query_Results_Iceberg'
NUM_ESECUZIONI = 3  # Prima esecuzione + almeno due successive per la mediana.

# Stato della sola run corrente. Gli script di prova non devono modificarlo.
_active_dataset = None
_capture_query_results = False
_query_index = 0
_query_results = {}
_capture_overhead = 0.0


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


def _store_query_result(columns, rows, name):
    """Memorizza la prima esecuzione della query nel dataset corrente.

    Query successive nella stessa fn() sono distinte tramite indice progressivo.
    Lo stesso indice fra 1M e 10M confluisce nello stesso CSV.
    """
    global _query_index
    if not _capture_query_results:
        return
    tag = _active_dataset or _tag_from_name(name)
    if not tag:
        raise RuntimeError('Impossibile associare il risultato a un dataset')

    _query_index += 1
    entry = _query_results.setdefault(_query_index, {'columns': [], 'rows': []})
    for col in columns:
        if col != 'dataset' and col not in entry['columns']:
            entry['columns'].append(col)

    # Un campo "dataset" già restituito dalla query sarebbe ambiguo: la colonna
    # dataset del CSV indica sempre la taglia del benchmark (1M oppure 10M).
    for row in rows:
        record = {'dataset': tag}
        record.update({
            col: _csv_value(value)
            for col, value in zip(columns, row)
            if col != 'dataset'
        })
        entry['rows'].append(record)


def timed_query(con, sql, params=None, *, name=None, preview=PREVIEW_ROWS):
    started = time.perf_counter()
    cur = con.execute(sql, [] if params is None else params)
    rows = cur.fetchall()
    seconds = time.perf_counter() - started
    columns = [col[0] for col in cur.description]

    # L'esportazione viene eseguita fuori dalla misurazione della query.
    global _capture_overhead
    if _capture_query_results:
        capture_started = time.perf_counter()
        _store_query_result(columns, rows, name)
        _capture_overhead += time.perf_counter() - capture_started

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
    """Un CSV delle prestazioni per prova, con tempi distinti per taglia."""
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


def _write_query_csvs(test_id):
    """CSV per i risultati effettivi di timed_query(), senza file duplicati.

    Una query: <test_id>.csv
    Piu' query: <test_id>_01.csv, <test_id>_02.csv, ...
    """
    QUERY_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    multiple = len(_query_results) > 1
    for number, (index, data) in enumerate(sorted(_query_results.items()), start=1):
        suffix = f'_{number:02d}' if multiple else ''
        destination = QUERY_RESULTS_DIR / f'{test_id}{suffix}.csv'
        with destination.open('w', newline='', encoding='utf-8-sig') as fh:
            writer = csv.DictWriter(
                fh, fieldnames=['dataset', *data['columns']], extrasaction='ignore'
            )
            writer.writeheader()
            writer.writerows(data['rows'])
        paths.append(destination)
    return paths


def _remove_stale_query_csvs(test_id, current_paths):
    """Elimina solo vecchi file associati alla prova, mai i performance CSV."""
    keep = set(current_paths)
    candidates = [QUERY_RESULTS_DIR / f'{test_id}.csv']
    candidates.extend(QUERY_RESULTS_DIR.glob(f'{test_id}_query_*.csv'))
    # Nomi progressivi nuovi, anche da run precedenti con piu' query.
    candidates.extend(
        p for p in QUERY_RESULTS_DIR.glob(f'{test_id}_*.csv')
        if p.stem[len(test_id) + 1:].isdigit()
    )
    for path in set(candidates) - keep:
        if path.is_file():
            path.unlink()


def _write_test_result_csv(test_id, results_by_tag):
    """Salva il risultato strutturato della prima esecuzione per dataset.

    Supporta i dizionari restituiti da O1, C1, C2 e O4, con colonne
    determinate dalla prova. Dizionari e liste annidati diventano JSON
    all'interno di una cella CSV, senza perdere i valori originali.
    """
    if not results_by_tag:
        return None

    columns = []
    records = []
    for tag, result in results_by_tag.items():
        if not isinstance(result, dict):
            raise TypeError(
                f"Risultato {test_id}/{tag}: atteso dict, ricevuto "
                f"{type(result).__name__}"
            )
        record = {'dataset': tag}
        for key, value in result.items():
            if key == 'dataset':
                continue  # 'dataset' identifica sempre 1M o 10M.
            if key not in columns:
                columns.append(key)
            record[key] = _csv_value(value)
        records.append(record)

    QUERY_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    destination = QUERY_RESULTS_DIR / f'{test_id}.csv'
    with destination.open('w', newline='', encoding='utf-8-sig') as fh:
        writer = csv.DictWriter(
            fh, fieldnames=['dataset', *columns], extrasaction='ignore'
        )
        writer.writeheader()
        writer.writerows(records)
    return destination


def _results_for_dataset(returned, tag):
    """Recupera l'output di execute() relativo al dataset in misurazione.

    Gli script usano in genere {tag: {campi...}}. Si accetta anche
    direttamente {campi...} per prove che elaborano un singolo dataset.
    """
    if returned is None:
        return None
    if not isinstance(returned, dict):
        raise TypeError('execute() deve restituire un dizionario oppure None')
    if tag in returned:
        value = returned[tag]
        if not isinstance(value, dict):
            raise TypeError(f'Il risultato del dataset {tag} deve essere un dict')
        return value
    # Se il dizionario è indicizzato per altre taglie, non confonderlo
    # con un insieme di campi della prova.
    if any(key in MINIO_FOLDERS or key in TABLES for key in returned):
        raise KeyError(f'execute() non ha restituito il dataset richiesto: {tag}')
    return returned


def run(test_id, fn):
    global _active_dataset, _capture_query_results, _query_index, _query_results
    global _capture_overhead

    if not isinstance(NUM_ESECUZIONI, int) or NUM_ESECUZIONI < 3:
        raise ValueError('NUM_ESECUZIONI deve essere un intero maggiore o uguale a 3')

    # Congela le taglie configurate. TABLES viene modificato IN PLACE,
    # così anche gli script che importano TABLES con "from common import TABLES"
    # vedono soltanto il dataset attualmente misurato.
    configured_tables = dict(TABLES)
    times_by_tag = {}
    structured_results = {}
    active_tag = None
    _query_results = {}

    try:
        for tag, table_name in configured_tables.items():
            active_tag = tag
            TABLES.clear()
            TABLES[tag] = table_name

            times = []
            times_by_tag[tag] = times
            for execution_index in range(NUM_ESECUZIONI):
                _active_dataset = tag
                _capture_query_results = execution_index == 0
                _query_index = 0
                _capture_overhead = 0.0

                started = time.perf_counter()
                returned = fn()
                # Esclude dai tempi totali il costo aggiuntivo di esportazione.
                times.append(max(0.0, time.perf_counter() - started - _capture_overhead))

                if execution_index == 0:
                    result = _results_for_dataset(returned, tag)
                    if result is not None:
                        structured_results[tag] = result
                _capture_query_results = False

        performance_path = _write_csv(test_id, times_by_tag)
        if _query_results:
            # Se timed_query() e' stata usata, conserva solo i risultati SQL,
            # non il riepilogo (anteprima/tempo) restituito da execute().
            query_paths = _write_query_csvs(test_id)
        else:
            # Prove senza timed_query() (ad es. O1, C1, C2 e O4).
            structured_path = _write_test_result_csv(test_id, structured_results)
            query_paths = [structured_path] if structured_path is not None else []
        _remove_stale_query_csvs(test_id, query_paths)
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
            'file_csv_performance': str(performance_path),
            'file_csv_query': [str(path) for path in query_paths],
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
        _active_dataset = None
        _capture_query_results = False
        _query_index = 0
        _query_results = {}
        TABLES.clear()
        TABLES.update(configured_tables)
