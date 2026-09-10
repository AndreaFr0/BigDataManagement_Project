from pyiceberg.catalog import load_catalog
import pyarrow as pa


# Carico catalogo Iceberg
catalog = load_catalog("default")

# Carico tabella
table = catalog.load_table("test.prodotti")


print("Metadata corrente:")
print(table.metadata_location)


# Leggo dati attuali
df = table.scan().to_pandas()

print("\nPrima della cancellazione:")
print(df)


# ===========================
# ID del prodotto da eliminare
# ===========================

id_da_eliminare = 7


# Elimino tutte le righe con quell'id
df = df[df["id"] != id_da_eliminare]


print("\nDopo la cancellazione:")
print(df)


# ===========================
# Ricreo tabella PyArrow
# mantenendo lo schema Iceberg
# ===========================

schema_arrow = pa.schema([
    pa.field("id", pa.int64(), nullable=False),
    pa.field("nome", pa.string(), nullable=True),
    pa.field("prezzo", pa.float64(), nullable=True),
    pa.field("quantita", pa.int64(), nullable=True)
])


nuovi_dati = pa.Table.from_pydict(
    {
        "id": df["id"].tolist(),
        "nome": df["nome"].tolist(),
        "prezzo": df["prezzo"].tolist(),
        "quantita": df["quantita"].tolist()
    },
    schema=schema_arrow
)


# ===========================
# Creo nuovo snapshot
# ===========================

table.overwrite(nuovi_dati)


print("\nProdotto eliminato correttamente")


# Ricarico metadata aggiornato
table = catalog.load_table("test.prodotti")

print("\nNuovo metadata:")
print(table.metadata_location)