"""B4: media di gennaio vs luglio per tipo, per l'anno esplicito.
Filtri per intervallo temporale (più favorevoli al pruning di EXTRACT sul timestamp).
Questa query misura il tempo: NON prova da sola l'effettivo numero di file evitati.
"""
from common import for_each, run

YEAR = 2024


def execute():
    return for_each('B4', lambda src, tag: (
        f'''WITH periodi AS (
                SELECT tipo, valore, 'gennaio' AS mese
                FROM {src} WHERE ts >= TIMESTAMPTZ '{YEAR}-01-01 00:00:00+00'
                                 AND ts < TIMESTAMPTZ '{YEAR}-02-01 00:00:00+00'
                UNION ALL
                SELECT tipo, valore, 'luglio' AS mese
                FROM {src} WHERE ts >= TIMESTAMPTZ '{YEAR}-07-01 00:00:00+00'
                                 AND ts < TIMESTAMPTZ '{YEAR}-08-01 00:00:00+00'
            )
            SELECT tipo,
                   AVG(valore) FILTER (WHERE mese = 'gennaio') AS media_gennaio,
                   AVG(valore) FILTER (WHERE mese = 'luglio') AS media_luglio,
                   AVG(valore) FILTER (WHERE mese = 'luglio')
                     - AVG(valore) FILTER (WHERE mese = 'gennaio') AS differenza,
                   COUNT(*) FILTER (WHERE mese = 'gennaio') AS letture_gennaio,
                   COUNT(*) FILTER (WHERE mese = 'luglio') AS letture_luglio
            FROM periodi GROUP BY tipo ORDER BY tipo''', []))


if __name__ == '__main__':
    run('B4', execute)
