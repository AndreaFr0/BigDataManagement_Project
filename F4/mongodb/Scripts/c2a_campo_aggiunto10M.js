
const coll = db.getCollection("letture_10M");

const inizio = new Date();

// Aggiunge il nuovo campo ai documenti che ancora non lo possiedono
const esito = coll.updateMany(
  { canale_radio: { $exists: false } },
  { $set: { canale_radio: "LoRaWAN" } }
);

const fine = new Date();

// Verifica dei risultati
const totale = coll.countDocuments();
const aggiornati = esito.modifiedCount;
const senzaCampo = coll.countDocuments({
  canale_radio: { $exists: false }
});

print("=== C2a — Campo aggiunto al dataset 1M ===");
print("Collezione             : letture_1M");
print("Documenti totali       : " + totale);
print("Documenti modificati   : " + aggiornati);
print("Documenti senza campo  : " + senzaCampo);
print("Tempo totale           : " + (fine - inizio) + " ms");

// Visualizza un documento aggiornato
const esempio = coll.findOne({
  canale_radio: { $exists: true }
});

print("");
print("Esempio di documento aggiornato:");
printjson(esempio);
