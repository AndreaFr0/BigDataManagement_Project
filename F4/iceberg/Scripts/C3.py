"""C3: snapshot Iceberg disponibili, tempo per recuperarli e tentativo di time travel.
Sceglie l'ultimo snapshot precedente, se esiste. Non modifica i dati.
"""
from common import run, duck, metadata_path, lit, scan, timed_query, TABLES, not_executed


def execute():
    con = duck()
    out = {}
    try:
        for tag in TABLES:
            path = metadata_path(tag)
            snapshots = timed_query(con, f'SELECT * FROM iceberg_snapshots({lit(path)}) ORDER BY sequence_number DESC',
                                    name=f'C3_snapshots_{tag}')
            # La funzione fa una seconda query per ottenere l'identificativo dell'eventuale snapshot storico:
            ids = timed_query(con, f'SELECT snapshot_id FROM iceberg_snapshots({lit(path)}) ORDER BY sequence_number DESC',
                              name=f'C3_ids_{tag}')
            items = ids['anteprima']
            if len(items) >= 2:
                prev = int(items[1]['snapshot_id'])
                historical = timed_query(con, f'SELECT COUNT(*) AS righe_snapshot_precedente FROM {scan(path, prev)}',
                                         name=f'C3_time_travel_{tag}')
                previous = {'snapshot_id': prev, 'conteggio': historical}
            else:
                previous = not_executed('Manca uno snapshot precedente visibile: non è possibile ricostruire lo stato prima del caricamento.')
            out[tag] = {'tabella': TABLES[tag], 'snapshots': snapshots, 'id_snapshot': ids,
                        'time_travel': previous}
        return out
    finally:
        con.close()


if __name__ == '__main__':
    run('C3', execute)
