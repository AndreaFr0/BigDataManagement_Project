
// C5 — Valore medio della batteria presente nel payload JSON
// Esecuzione:
// mongosh "mongodb://localhost:27017/progetto_db" --file c5_media_batteria.js

const coll = db.getCollection("letture_10M");

const totale = coll.countDocuments();

const risultato = coll.aggregate([
  {
    $addFields: {
      payload_obj: {
        $function: {
          body: function (str) {
            try {
              return JSON.parse(str);
            } catch (e) {
              return null;
            }
          },
          args: ["$payload"],
          lang: "js"
        }
      }
    }
  },
  {
    $match: {
      "payload_obj.batteria_pct": { $type: "number" }
    }
  },
  {
    $group: {
      _id: null,
      batteria_media: { $avg: "$payload_obj.batteria_pct" },
      letture_con_batteria: { $sum: 1 },
      batteria_minima: { $min: "$payload_obj.batteria_pct" },
      batteria_massima: { $max: "$payload_obj.batteria_pct" }
    }
  }
]).toArray();

if (risultato.length > 0) {
  const r = risultato[0];

  print("===== RISULTATO C5 =====");
  print("Totale letture: " + totale);
  print("Letture con batteria: " + r.letture_con_batteria);
  print("Letture senza batteria: " + (totale - r.letture_con_batteria));
  print("Percentuale con batteria: " +
    (r.letture_con_batteria / totale * 100).toFixed(2) + "%");
  print("Batteria media: " + r.batteria_media.toFixed(2) + "%");
  print("Batteria minima: " + r.batteria_minima + "%");
  print("Batteria massima: " + r.batteria_massima + "%");
} else {
  print("Nessun dato valido trovato.");
}
