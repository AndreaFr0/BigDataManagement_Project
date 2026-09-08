from pyiceberg.catalog import load_catalog
import pyarrow as pa


# Carico il catalogo Iceberg
catalog = load_catalog("default")


# Carico la tabella esistente
table = catalog.load_table("test.prodotti")


print("Metadata corrente:")
print(table.metadata_location)


# Schema PyArrow compatibile con Iceberg
schema_arrow = pa.schema([
    pa.field("id", pa.int64(), nullable=False),
    pa.field("nome", pa.string(), nullable=True),
    pa.field("prezzo", pa.float64(), nullable=True)
])


# Nuovi prodotti da inserire
nuovi_prodotti = pa.Table.from_pydict(
    {
        "id": [5, 6, 7],
        "nome": [
            "quaderno",
            "righello",
            "temperino"
        ],
        "prezzo": [
            2.50,
            1.20,
            0.80
        ]
    },
    schema=schema_arrow
)


print("Dati da inserire:")
print(nuovi_prodotti)


# Append: crea un nuovo snapshot Iceberg
table.append(nuovi_prodotti)


print("Inserimento completato")


# Ricarico la tabella per vedere il nuovo metadata
table = catalog.load_table("test.prodotti")

print("Nuovo metadata:")
print(table.metadata_location)