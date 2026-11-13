"""B2: 10 sensori con più letture fuori soglia.
Le soglie NON sono deducibili dal CSV: compilarle prima di eseguire.
"""
from common import for_each, run, not_executed

# Valori numerici nelle unità originali di ciascun tipo: sostituire None con soglie concordate.
SOGLIE_MASSIME = {
    'idrometrico': 100,   # es. cm
    'meteo': 40,          # es. °C
    'qualita_aria': 93,  # es. µg/m³
}
ONLY_VALID = False


def execute():
    if any(value is None for value in SOGLIE_MASSIME.values()):
        return not_executed('Soglie fisiche non fornite: non è corretto inventarle o confrontare tipi con unità diverse.',
                            next_step='Inserire soglie in SOGLIE_MASSIME e verificare le unità di misura per tipo.')
    if any(not isinstance(v, (int, float)) for v in SOGLIE_MASSIME.values()):
        raise ValueError('SOGLIE_MASSIME deve contenere valori numerici')
    cond = ' AND qualita = 1' if ONLY_VALID else ''
    return for_each('B2', lambda src, tag: (
        f'''SELECT sensor_id, COUNT(*) AS letture_fuori_soglia
            FROM {src}
            WHERE ((tipo = 'idrometrico' AND valore > ?)
                OR (tipo = 'meteo' AND valore > ?)
                OR (tipo = 'qualita_aria' AND valore > ?))
                {cond}
            GROUP BY sensor_id ORDER BY letture_fuori_soglia DESC, sensor_id LIMIT 10''',
        [SOGLIE_MASSIME['idrometrico'], SOGLIE_MASSIME['meteo'], SOGLIE_MASSIME['qualita_aria']]))


if __name__ == '__main__':
    run('B2', execute)
