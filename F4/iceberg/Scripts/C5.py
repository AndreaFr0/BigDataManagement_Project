"""C5: media del campo numerico opzionale batteria_pct nel payload Iceberg.

Gestisce payload STRUCT/MAP, JSON e testo JSON. I campi assenti o non
numerici vengono esclusi dalla media ma conteggiati separatamente.
I risultati di 1M e 10M sono salvati da common.py in Results/C5.csv.
Il tempo di ciascuna query include execute() e fetchall(), non la scrittura CSV.
"""
from common import for_each, run

CAMPO_PAYLOAD = 'batteria_pct'


def execute():
    def build_query(src, tag):
        # Una stringa JSON deve essere interpretata come JSON, non codificata
        # ulteriormente con to_json(). STRUCT/MAP invece sono convertiti in JSON.
        query = f"""
            WITH dati AS (
                SELECT
                    CASE
                        WHEN typeof(payload) = 'VARCHAR'
                            THEN TRY_CAST(payload AS JSON)
                        ELSE to_json(payload)
                    END AS payload_json
                FROM {src}
            ),
            valori AS (
                SELECT TRY_CAST(
                    json_extract_string(payload_json, '$.{CAMPO_PAYLOAD}')
                    AS DOUBLE
                ) AS batteria_pct
                FROM dati
            )
            SELECT
                AVG(batteria_pct) AS media_batteria_pct,
                COUNT(batteria_pct) AS letture_con_batteria_pct,
                COUNT(*) - COUNT(batteria_pct) AS letture_senza_batteria_pct,
                COUNT(*) AS letture_totali
            FROM valori
        """
        return query, []

    return for_each('C5', build_query)


if __name__ == '__main__':
    run('C5', execute)
