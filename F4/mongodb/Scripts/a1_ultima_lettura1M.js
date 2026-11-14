// A1 — Ultima lettura del sensore S-042
// Esecuzione da terminale:
//   mongosh "mongodb://localhost:27017/iot_urbano" --file a1_ultima_lettura.js

const risultato = db.letture_1M
  .find({ sensor_id: "S-042" })
  .sort({ ts: -1 })
  .limit(1)
  .toArray();

print("=== A1 — Ultima lettura S-042 ===");
printjson(risultato);
