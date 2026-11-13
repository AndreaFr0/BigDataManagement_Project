"""Q0: controllo conteggio e somma in Iceberg; NON verifica altri store non configurati."""
from common import for_each, run


def execute():
    return {
        'iceberg': for_each('Q0', lambda src, tag: (
            f'''SELECT COUNT(*) AS conteggio,
                       COUNT(valore) AS valori_non_null,
                       SUM(CAST(valore AS DECIMAL(24, 4))) AS somma_valori
                FROM {src}''', [])),
    }


if __name__ == '__main__':
    run('Q0', execute)
