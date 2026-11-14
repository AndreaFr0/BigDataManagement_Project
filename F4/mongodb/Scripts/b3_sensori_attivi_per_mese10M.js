// B3 — Numero di sensori distinti attivi, per mese
// Esecuzione da terminale:
//   mongosh "mongodb://localhost:27017/iot_urbano" --file b3_sensori_attivi_per_mese.js

const risultato = db.letture_1M.aggregate([
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
          unit: "month"
        }
      },
      sensori: { $addToSet: "$sensor_id" }
    }
  },
  {
    $project: {
      _id: 1,
      n_sensori_distinti: { $size: "$sensori" }
    }
  },
  { $sort: { _id: 1 } }
]).toArray();

print("=== B3 — Sensori distinti attivi per mese ===");
printjson(risultato);
