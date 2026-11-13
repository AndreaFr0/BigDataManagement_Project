"""B1: media oraria idrometrica negli ultimi 6 mesi coperti dal dataset."""
from common import for_each, run

MONTHS = 6
ONLY_VALID = False  # True -> considera soltanto qualita = 1


def execute():
    valid_filter = ' AND d.qualita = 1' if ONLY_VALID else ''
    return for_each('B1', lambda src, tag: (
        f'''WITH reference AS (SELECT MAX(ts) AS t_max FROM {src})
            SELECT date_trunc('hour', d.ts) AS ora_utc,
                   AVG(d.valore) AS media_idrometrica,
                   COUNT(d.valore) AS letture_valide_numericamente
            FROM {src} d CROSS JOIN reference r
            WHERE d.tipo = 'idrometrico'
              AND d.ts > r.t_max - INTERVAL '{MONTHS} months'
              AND d.ts <= r.t_max {valid_filter}
            GROUP BY 1 ORDER BY 1''', []))


if __name__ == '__main__':
    run('B1', execute)
