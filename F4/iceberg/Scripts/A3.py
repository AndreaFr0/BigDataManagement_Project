"""A3: numero e ID dei sensori con letture negli ultimi 5 min dei dati.
Snapshot storico: non equivale a monitoraggio live.
"""
from common import for_each, run

MINUTES = 5


def execute():
    return for_each('A3', lambda src, tag: (
        f'''WITH reference AS (SELECT MAX(ts) AS t_max FROM {src})
            SELECT COUNT(DISTINCT sensor_id) AS sensori_attivi,
                   LIST(DISTINCT sensor_id ORDER BY sensor_id) AS elenco_sensori
            FROM {src}, reference AS r
            WHERE ts > r.t_max - INTERVAL '{MINUTES} minutes' AND ts <= r.t_max''', []))


if __name__ == '__main__':
    run('A3', execute)
