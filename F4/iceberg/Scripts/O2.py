
"""O2: numero file dati Iceberg nello snapshot corrente
e numero totale di snapshot registrati.
"""

from common import (
    duck,
    run,
    TABLES,
    metadata_path,
    lit,
    timed_query,
)


def execute():

    con = duck()
    out = {}

    try:

        for tag in TABLES:

            path = metadata_path(tag)

            manifest_sql = f"""
                SELECT
                    COUNT(DISTINCT file_path)
                        AS file_dati_correnti,
                    COUNT(DISTINCT manifest_path)
                        AS manifest_distinti,
                    COALESCE(SUM(record_count), 0)
                        AS record_dichiarati
                FROM iceberg_metadata({lit(path)})
                WHERE manifest_content = 'DATA'
                  AND status IN ('ADDED', 'EXISTING')
            """

            snapshots_sql = f"""
                SELECT
                    COUNT(*) AS numero_snapshots
                FROM iceberg_snapshots({lit(path)})
            """

            out[tag] = {
                "file_metadata": timed_query(
                    con,
                    manifest_sql,
                    name=f"O2_file_{tag}"
                ),
                "snapshots": timed_query(
                    con,
                    snapshots_sql,
                    name=f"O2_snapshots_{tag}"
                ),
            }

        return out

    finally:
        con.close()


if __name__ == "__main__":
    run("O2", execute)
