
const coll = db.getCollection("letture_10M");

const inizio = new Date();

// Rinomina il campo in tutti i documenti della collezione
const risultato = coll.updateMany(
  { unita: { $exists: true } },
  { $rename: { "unita": "unita_misura" } }
);

const fine = new Date();

// Verifica del risultato
const totale = coll.countDocuments();
const conVecchioCampo = coll.countDocuments({
  unita: { $exists: true }
});
const conNuovoCampo = coll.countDocuments({
  unita_misura: { $exists: true }
});

print("=== C2b — Campo rinominato (unita -> unita_misura) ===");
print("Collezione             : letture_1M");
print("Documenti totali       : " + totale);
print("Documenti modificati   : " + risultato.modifiedCount);
print("Documenti con unita    : " + conVecchioCampo);
print("Documenti con unita_misura: " + conNuovoCampo);
print("Tempo                  : " + (fine - inizio) + " ms");

print("");
print("Esempio di documento aggiornato:");

const esempio = coll.findOne({
  unita_misura: { $exists: true }
});

printjson(esempio);

