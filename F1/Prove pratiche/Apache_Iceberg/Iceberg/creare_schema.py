from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField, LongType, StringType
import pyarrow as pa

catalog = load_catalog("default")

table = catalog.load_table("test.prodotti")

print(table.metadata_location)

schema_arrow = pa.schema([
    pa.field("id", pa.int64(), nullable=False),
    pa.field("nome", pa.string(), nullable=True),
    pa.field("prezzo",pa.float64(), nullable=True)
])


dati = pa.Table.from_pydict(
    {
        "id": [1, 2, 3],
        "nome": ["penna", "matita", "gomma"],
        "prezzo": [0.77, 0.69, 1.20]
    },
    schema=schema_arrow
)

print(dati.schema)

table.append(dati)