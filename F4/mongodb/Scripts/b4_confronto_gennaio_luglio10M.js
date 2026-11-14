// B4 — Confronto fra la media di gennaio e quella di luglio, per tipo di sensore
// Esecuzione da terminale:
//   mongosh "mongodb://localhost:27017/iot_urbano" --file b4_confronto_gennaio_luglio.js

const risultato = db.letture_10M.aggregate([
  {
    $addFields: {
      ts_date: { $toDate: "$ts" }
    }
  },
  {
    $match: {
      $or: [
        {
          ts_date: {
            $gte: ISODate("2024-01-01T00:00:00Z"),
            $lt: ISODate("2024-02-01T00:00:00Z")
          }
        },
        {
          ts_date: {
            $gte: ISODate("2024-07-01T00:00:00Z"),
            $lt: ISODate("2024-08-01T00:00:00Z")
          }
        }
      ]
    }
  },
  {
    $group: {
      _id: {
        tipo: "$tipo",
        mese: { $month: "$ts_date" }
      },
      media_valore: { $avg: "$valore" },
      n_letture: { $sum: 1 }
    }
  },
  {
    $sort: {
      "_id.tipo": 1,
      "_id.mese": 1
    }
  }
]).toArray();

print("=== B4 — Media gennaio vs luglio, per tipo ===");
printjson(risultato);
