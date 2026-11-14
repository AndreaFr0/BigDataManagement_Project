// B1 — Media oraria del livello idrometrico, ultimi 6 mesi, tutti i sensori
// Esecuzione da terminale:
//   mongosh "mongodb://localhost:27017/iot_urbano" --file b1_media_oraria_idrometrico.js
//
// Richiede MongoDB >= 5.0 per $dateTrunc (va bene con la linea 8.x del progetto).

const risultato = db.letture_1M.aggregate([
  {
    $match: {
      tipo: "idrometrico",
      ts: {
        $gte: "2024-07-01T00:00:00Z",
        $lte: "2024-12-31T23:59:59Z"
      }
    }
  },
  {
    $addFields: {
      ts_date: { $toDate: "$ts" }
    }
  },
  {
    $group: {
      _id: {
        $dateTrunc: {
          date: "$ts_date",
          unit: "hour"
        }
      },
      media_valore: { $avg: "$valore" },
      n_letture: { $sum: 1 }
    }
  },
  { $sort: { _id: 1 } }
]).toArray();

print("=== B1 — Media oraria idrometrico (ultimi 6 mesi) ===");
print(`Bucket orari restituiti: ${risultato.length}`);
print("Prime 10 righe:");
printjson(risultato.slice(0, 10));
