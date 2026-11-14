// B2 — I 10 sensori con più letture "fuori soglia" sull'intero storico
// Esecuzione da terminale:
//   mongosh "mongodb://localhost:27017/iot_urbano" --file b2_top10_fuori_soglia.js
//
// Definizione di "fuori soglia" usata qui: qualita in {0,2} (invalida/sospetta).
// Va dichiarata esplicitamente in D2: è un'interpretazione, non un dato del
// modello. In alternativa si può filtrare su valore > soglia per tipo
// (vedi commento in fondo al file).

const risultato = db.letture_1M.aggregate([
  { $match: { qualita: { $in: [0, 2] } } },
  { $group: { _id: "$sensor_id", n_fuori_soglia: { $sum: 1 } } },
  { $sort: { n_fuori_soglia: -1 } },
  { $limit: 10 }
]).toArray();

print("=== B2 — Top 10 sensori per letture fuori soglia (qualita in {0,2}) ===");
printjson(risultato);

// Variante con soglia sul valore, specifica per tipo di sensore:
//
// db.letture.aggregate([
//   { $match: { $or: [
//       { tipo: "idrometrico",  valore: { $gt: 150 } },
//       { tipo: "meteo",        valore: { $gt: 38 } },
//       { tipo: "qualita_aria", valore: { $gt: 100 } }
//   ]}},
//   { $group: { _id: "$sensor_id", n_fuori_soglia: { $sum: 1 } } },
//   { $sort: { n_fuori_soglia: -1 } },
//   { $limit: 10 }
// ])
