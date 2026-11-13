"""A1: ultima lettura S-042; una query indipendente per ciascuna taglia."""
from common import for_each, run

SENSOR_ID = 'S-042'


def execute():
    return for_each('A1', lambda src, tag: (
        f'''SELECT sensor_id, ts, tipo, valore, unita, qualita
            FROM {src}
            WHERE sensor_id = ?
            ORDER BY ts DESC LIMIT 1''', [SENSOR_ID]))


if __name__ == '__main__':
    run('A1', execute)
