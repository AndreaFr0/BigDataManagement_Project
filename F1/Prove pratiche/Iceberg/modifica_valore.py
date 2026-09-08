from pyiceberg.catalog import load_catalog
import pyarrow as pa


catalog = load_catalog("default")

table = catalog.load_table("test.prodotti")


df = table.scan().to_pandas()

print("Prima:")
print(df)


df.loc[df["id"] == 1, "quantita"] = 3
df.loc[df["id"] == 2, "quantita"] = 5
df.loc[df["id"] == 3, "quantita"] = 20
df.loc[df["id"] == 5, "quantita"] = 18
df.loc[df["id"] == 6, "quantita"] = 7
df.loc[df["id"] == 7, "quantita"] = 8



print("Dopo:")
print(df)


schema = pa.schema([
    pa.field("id", pa.int64(), nullable=False),
    pa.field("nome", pa.string(), nullable=True),
    pa.field("prezzo", pa.float64(), nullable=True),
    pa.field("quantita", pa.int64(), nullable=True),
])


arrow_table = pa.Table.from_pydict(
    {
        "id": df["id"].tolist(),
        "nome": df["nome"].tolist(),
        "prezzo": df["prezzo"].tolist(),
        "quantita": df["quantita"].tolist()
    },
    schema=schema
)


table.overwrite(arrow_table)

print("Aggiornamento completato")