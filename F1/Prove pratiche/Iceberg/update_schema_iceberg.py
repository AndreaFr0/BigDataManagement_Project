from pyiceberg.catalog import load_catalog
import pyarrow as pa
import pandas as pd
from pyiceberg.types import DoubleType
from pyiceberg.types import LongType


# Carico il catalogo Iceberg (PostgreSQL)
catalog = load_catalog("default")

# Carico la tabella
table = catalog.load_table("test.prodotti")


# ===========================
# 1) Aggiornamento Schema
# ===========================

if "quantita" not in [field.name for field in table.schema().fields]:
    with table.update_schema() as update:
        update.add_column(
            "quantita",
            LongType()
        )

    print("Colonna quantità aggiunta")
else:
    print("Colonna quantità già presente")


# Ricarico la tabella dopo la modifica dello schema
table = catalog.load_table("test.prodotti")

# ===========================
# 2) Leggo i dati esistenti
# ===========================

df = table.scan().to_pandas()

print("Dati prima:")
print(df)


# ===========================
# 3) Inserisco i prezzi
# ===========================

df.loc[df["id"] == 1, "quantita"] = 10
df.loc[df["id"] == 2, "quantita"] = 14
df.loc[df["id"] == 3, "quantita"] = 22
df.loc[df["id"] == 4, "quantita"] = 4
df.loc[df["id"] == 5, "quantita"] = 8
df.loc[df["id"] == 6, "quantita"] = 19
df.loc[df["id"] == 7, "quantita"] = 16


# ===========================
# 4) Creo PyArrow rispettando Iceberg
# ===========================

arrow_table = pa.table({
    "id": pa.array(df["id"], type=pa.int64()),
    "nome": pa.array(df["nome"], type=pa.string()),
    "prezzo": pa.array(df["prezzo"], type=pa.float64()),
    "quantita": pa.array(df["quantita"], type=pa.int64())
})

# ===========================
# 5) Riscrivo lo snapshot
# ===========================

table.overwrite(arrow_table)

print("Quantità aggiunte correttamente")
