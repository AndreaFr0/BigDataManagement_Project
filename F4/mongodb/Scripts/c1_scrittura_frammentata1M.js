
function generaLotto(n, offset) {
  const tipi = ["idrometrico", "meteo", "qualita_aria"];

  const unitaPerTipo = {
    idrometrico: "cm",
    meteo: "°C",
    qualita_aria: "µg/m³"
  };

  const lotto = [];

  for (let i = 0; i < n; i++) {
    const numSensore = ((offset + i) % 200) + 1;
    const tipo = tipi[numSensore % 3];

    lotto.push({
      sensor_id: "S-" + String(numSensore).padStart(3, "0"),
      ts: new Date().toISOString(),
      tipo: tipo,
      valore: Math.round(Math.random() * 10000) / 100,
      unita: unitaPerTipo[tipo],
      lat: 40.352 + (Math.random() - 0.5) * 0.24,
      lon: 18.170 + (Math.random() - 0.5) * 0.24,
      qualita: 1,
      payload: ""
    });
  }

  return lotto;
}

function eseguiTest(nomeCollezione) {
  const coll = db.getCollection(nomeCollezione);

  const NUM_RIPETIZIONI = 100;
  const LETTURE_PER_RIPETIZIONE = 10000;

  const prima = coll.countDocuments();
  const inizio = new Date();

  for (let i = 0; i < NUM_RIPETIZIONI; i++) {
    const lotto = generaLotto(
      LETTURE_PER_RIPETIZIONE,
      i * LETTURE_PER_RIPETIZIONE
    );

    coll.insertMany(lotto, { ordered: false });
  }

  const fine = new Date();
  const dopo = coll.countDocuments();

  const tempoMs = fine - inizio;
  const inseriti = dopo - prima;

  print("");
  print("=== C1 — " + nomeCollezione + " ===");
  print("Scritture effettuate : " + NUM_RIPETIZIONI);
  print("Letture per scrittura: " + LETTURE_PER_RIPETIZIONE);
  print("Documenti iniziali   : " + prima);
  print("Documenti inseriti   : " + inseriti);
  print("Documenti finali     : " + dopo);
  print("Tempo totale         : " + tempoMs + " ms");
  print("Throughput           : " +
        (inseriti / (tempoMs / 1000)).toFixed(2) +
        " documenti/sec");
}

eseguiTest("letture_1M");

