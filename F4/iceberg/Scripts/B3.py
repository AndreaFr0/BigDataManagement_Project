"""B3: sensori distinti con almeno una lettura per mese sull'intero storico."""
from common import for_each, run


def execute():
    return for_each('B3', lambda src, tag: (
        f'''SELECT date_trunc('month', ts) AS mese_utc,
                   COUNT(DISTINCT sensor_id) AS sensori_attivi
            FROM {src}
            GROUP BY 1 ORDER BY 1''', []))


if __name__ == '__main__':
    run('B3', execute)
