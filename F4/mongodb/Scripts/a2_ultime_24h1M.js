// A2 — Letture del sensore S-042 nelle ultime 24 ore
// Esecuzione da terminale:
//   mongosh "mongodb://localhost:27017/iot_urbano" --file a2_ultime_24h.js
//
// Nota: "ultime 24 ore" è calcolato rispetto al timestamp massimo presente
// in collezione, non rispetto all'orario reale del sistema, perché il
// dataset è sintetico e fissato al 2024.

const ultimo = db.letture_1M
  .find()
  .sort({ ts: -1 })
  .limit(1)
  .next();

const ora_rif = new Date(ultimo.ts);
const inizio = new Date(ora_rif.getTime() - 24 * 60 * 60 * 1000);

const risultato = db.letture_1M
  .find({
    sensor_id: "S-042",
    ts: {
      $gte: inizio.toISOString(),
      $lte: ora_rif.toISOString()
    }
  })
  .sort({ ts: 1 })
  .toArray();

print("=== A2 — Letture S-042 nelle ultime 24h ===");
print(`Ora di riferimento : ${ora_rif.toISOString()}`);
print(`Inizio finestra     : ${inizio.toISOString()}`);
print(`Documenti trovati   : ${risultato.length}`);
print("Primi 20 risultati:");
printjson(risultato.slice(0, 20));
