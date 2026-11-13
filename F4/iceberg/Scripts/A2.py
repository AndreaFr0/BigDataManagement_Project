"""A2: letture del sensore nelle ultime 24 ore
rispetto alla sua ultima lettura disponibile.
"""

from common import for_each, run

SENSOR_ID = 'S-042'
HOURS = 24


def execute():
    return for_each('A2', lambda src, tag: (
        f"""
        WITH reference AS (
            SELECT MAX(ts) AS t_max
            FROM {src}
            WHERE sensor_id = ?
        )
        SELECT
            d.sensor_id,
            d.ts,
            d.tipo,
            d.valore,
            d.unita,
            d.qualita
        FROM {src} AS d
        CROSS JOIN reference AS r
        WHERE d.sensor_id = ?
          AND d.ts > r.t_max - INTERVAL '{HOURS} hours'
          AND d.ts <= r.t_max
        ORDER BY d.ts DESC
        """,
        [SENSOR_ID, SENSOR_ID]
    ))


if __name__ == '__main__':
    run('A2', execute)
