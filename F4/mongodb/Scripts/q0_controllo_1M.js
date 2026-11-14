
// Q0 — Controllo di correttezza: conteggio e somma dei valori
// Tabella: 1 milione di record
//
// Esecuzione da terminale:
//   mongosh "mongodb://localhost:27017/iot_urbano" --file q0_controllo_1M.js

const coll = db.letture_1M;

const risultato = coll.aggregate([
    {
        $group: {
            _id: null,
            conteggio: { $sum: 1 },
            somma_valori: { $sum: "$valore" }
        }
    }
]).toArray();

print("=== Q0 — Controllo di correttezza (1M) ===");

if (risultato.length === 0) {

    print("Collezione vuota.");

} else {

    print(`Documenti totali : ${risultato[0].conteggio}`);
    print(`Somma dei valori : ${risultato[0].somma_valori}`);
}
