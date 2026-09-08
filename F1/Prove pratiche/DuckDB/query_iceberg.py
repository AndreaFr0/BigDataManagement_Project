import duckdb

from pyiceberg.catalog import load_catalog

catalog = load_catalog("default")

table = catalog.load_table("test.prodotti")

metadata = table.metadata_location

print(metadata)

conn = duckdb.connect()

conn.execute("LOAD httpfs")
conn.execute("LOAD iceberg")

conn.execute("""
SET s3_endpoint='localhost:9000';
SET s3_access_key_id='admin';
SET s3_secret_access_key='admin12345';
SET s3_use_ssl=false;
SET s3_url_style='path';
""")

query = f"""
SELECT *
FROM iceberg_scan('{metadata}')
"""

risultato = conn.execute(query).fetchdf()

print(risultato)
