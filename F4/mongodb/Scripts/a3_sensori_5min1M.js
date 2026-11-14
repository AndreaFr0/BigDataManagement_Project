// A3 — Sensori distinti che hanno trasmesso negli ultimi 5 minuti
// Esecuzione da terminale:
//   mongosh "mongodb://localhost:27017/iot_urbano" --file a3_sensori_5min.js

// A3 — Sensori attivi negli ultimi 5 minuti

const coll = db.letture_1M;

const ultimo = coll.find()
  .sort({ ts: -1 })
  .limit(1)
  .next();

if (ultimo === null) {
    print("ERRORE: collezione vuota.");
} else {

    const ora_rif = new Date(ultimo.ts);
    const inizio = new Date(ora_rif.getTime() - 5 * 60 * 1000);

    const sensori = coll.distinct("sensor_id", {
        ts: {
            $gte: inizio.toISOString(),
            $lte: ora_rif.toISOString()
        }
    });

    print("=== A3 — Sensori attivi negli ultimi 5 minuti ===");
    print(`Ora di riferimento : ${ora_rif.toISOString()}`);
    print(`Inizio finestra     : ${inizio.toISOString()}`);
    print(`Sensori distinti trovati: ${sensori.length}`);
    printjson(sensori);

    if (sensori.length === 0) {
        print("NOTA: nessun sensore trovato nella finestra temporale.");
    }
}
