
const coll = db.getCollection("letture_1M");

// Verifica del tipo originale
const prima = coll.aggregate([
  {
    $group: {
      _id: { $type: "$qualita" },
      totale: { $sum: 1 }
    }
  }
]).toArray();

const inizio = new Date();

// Conversione del campo qualita in double
const risultato = coll.updateMany(
  {},
  [
    {
      $set: {
        qualita: { $toDouble: "$qualita" }
      }
    }
  ]
);

const fine = new Date();

// Verifica del tipo dopo la conversione
const dopo = coll.aggregate([
  {
    $group: {
      _id: { $type: "$qualita" },
      totale: { $sum: 1 }
    }
  }
]).toArray();

print("=== C2c — Tipo promosso (qualita: int -> double) ===");
print("Collezione: letture_1M");

print("");
print("Distribuzione dei tipi PRIMA:");
printjson(prima);

print("");
print("Distribuzione dei tipi DOPO:");
printjson(dopo);

print("");
print("Documenti modificati: " + risultato.modifiedCount);
print("Tempo               : " + (fine - inizio) + " ms");

// Esempio di documento aggiornato
print("");
print("Esempio di documento:");
printjson(coll.findOne());
