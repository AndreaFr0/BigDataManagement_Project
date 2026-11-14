
const coll = db.getCollection("letture_10M");

const sensore = "S-042";

// Conteggio prima della cancellazione
const primaDelete = coll.countDocuments({
  sensor_id: sensore
});

// Cancellazione
const inizio = new Date();

const risultato = coll.deleteMany({
  sensor_id: sensore
});

const fine = new Date();

// Conteggio dopo la cancellazione
const dopoDelete = coll.countDocuments({
  sensor_id: sensore
});

print("=== C4 — Cancellazione letture " + sensore + " ===");
print("Collezione           : letture_1M");
print("Documenti prima      : " + primaDelete);
print("Documenti eliminati  : " + risultato.deletedCount);
print("Documenti dopo       : " + dopoDelete);
print("Tempo                : " + (fine - inizio) + " ms");

print("");
print("Verifica:");
print("Cancellazione completata: " + (dopoDelete === 0));

print("");
print("NOTA:");
print("La deleteMany elimina definitivamente i documenti dalla collezione.");
print("WiredTiger non restituisce necessariamente subito lo spazio");
print("liberato al filesystem.");

print("");
print("Per valutare separatamente la compattazione:");
print("  db.runCommand({ compact: 'letture_1M' })");

print("");
print("Recuperabilità tramite time travel: NO.");
print("MongoDB non offre un meccanismo nativo di time travel per");
print("recuperare i documenti cancellati dalla collezione live.");
