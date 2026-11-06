#!/usr/bin/env python3
"""
Generatore di dati sintetici per il progetto "Tre modelli di dato per l'IoT urbano".

Modello logico (§5.5 della scheda progetto):
    sensor_id  stringa       es. S-042
    ts         timestamp UTC istante della lettura
    tipo       stringa       idrometrico | meteo | qualita_aria
    valore     numerico      valore della misura
    unita      stringa       unita' di misura
    lat, lon   numerico      posizione del sensore
    qualita    intero        flag di validita' (0=invalida, 1=valida, 2=sospetta)
    payload    struttura     campi aggiuntivi presenti solo su una parte dei sensori
                              (eterogeneita' intenzionale, usata dalle prove C2 e C5)

Requisiti rispettati (§5.2):
    - parametri: numero di sensori, periodo simulato, numero totale di record
    - seme fisso per il generatore casuale -> stessa esecuzione = stesso dataset
    - scrive su file (qui: CSV), che i caricatori dei tre store leggeranno

"""

import argparse
import json
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Configurazione del dominio (fissa: fa parte del "modello dati comune")
# ---------------------------------------------------------------------------

TIPI = ["idrometrico", "meteo", "qualita_aria"]
UNITA_PER_TIPO = {
    "idrometrico": "cm",
    "meteo": "°C",
    "qualita_aria": "µg/m³",
}

# Bounding box approssimativo dell'area urbana simulata (Lecce e dintorni,
# coerente con l'ambito "IoT urbano" del progetto UniSalento).
LAT_CENTRO, LON_CENTRO = 40.352, 18.170
SPREAD_GRADI = 0.12  # ~13 km di raggio

FIRMWARE_POSSIBILI = ["1.2.0", "1.3.1", "1.4.2", "1.4.3"]


def genera_anagrafica_sensori(n_sensori: int, rng: np.random.Generator) -> pd.DataFrame:
    """Assegna a ciascun sensore un tipo, una posizione fissa e se e' 'evoluto'
    (cioe' se manda telemetria aggiuntiva nel payload). Tutto e' deterministico
    rispetto al seme."""
    sensor_ids = [f"S-{i:03d}" for i in range(1, n_sensori + 1)]

    # split dei tipi il piu' possibile bilanciato ma non perfettamente uguale,
    # per non essere artificiosi
    tipo_pool = (
        [TIPI[0]] * round(n_sensori * 0.35)
        + [TIPI[1]] * round(n_sensori * 0.35)
        + [TIPI[2]] * n_sensori
    )[:n_sensori]
    while len(tipo_pool) < n_sensori:
        tipo_pool.append(rng.choice(TIPI))
    tipo_pool = np.array(tipo_pool)
    rng.shuffle(tipo_pool)

    lat = LAT_CENTRO + rng.uniform(-SPREAD_GRADI, SPREAD_GRADI, n_sensori)
    lon = LON_CENTRO + rng.uniform(-SPREAD_GRADI, SPREAD_GRADI, n_sensori)

    # ~30% dei sensori e' "di nuova generazione" e manda telemetria aggiuntiva
    # (batteria, potenza segnale, firmware) -> e' il campo che rende
    # interessanti le prove C2 (evoluzione schema) e C5 (valore su campo
    # presente solo su una parte dei sensori)
    evoluto = rng.random(n_sensori) < 0.30

    return pd.DataFrame(
        {
            "sensor_id": sensor_ids,
            "tipo": tipo_pool,
            "lat": lat.round(6),
            "lon": lon.round(6),
            "evoluto": evoluto,
        }
    )


def genera_letture(n_record: int, n_sensori: int, mesi: int, seme: int) -> pd.DataFrame:
    rng = np.random.default_rng(seme)

    anagrafica = genera_anagrafica_sensori(n_sensori, rng)

    # --- scelta del sensore per ciascun record --------------------------------
    idx = rng.integers(0, n_sensori, size=n_record)
    sensor_id = anagrafica["sensor_id"].to_numpy()[idx]
    tipo = anagrafica["tipo"].to_numpy()[idx]
    lat = anagrafica["lat"].to_numpy()[idx]
    lon = anagrafica["lon"].to_numpy()[idx]
    evoluto = anagrafica["evoluto"].to_numpy()[idx]

    # --- timestamp: distribuiti sull'intero periodo simulato -------------------
    inizio = pd.Timestamp("2024-01-01T00:00:00Z")
    periodo_secondi = int(pd.Timedelta(days=30.44 * mesi).total_seconds())
    offset_secondi = rng.integers(0, periodo_secondi, size=n_record)
    ts = inizio + pd.to_timedelta(offset_secondi, unit="s")
    ts = ts.round("min")  # letture al minuto

    mese_numero = ts.month.to_numpy()
    ora_del_giorno = ts.hour.to_numpy()

    # --- valore: dipende dal tipo, con stagionalita' e rumore -------------------
    valore = np.empty(n_record, dtype=float)

    m_idro = tipo == "idrometrico"
    m_meteo = tipo == "meteo"
    m_aria = tipo == "qualita_aria"

    # idrometrico: livello base 40-80 cm, picchi in autunno/inverno (piogge)
    stagionalita_idro = 20 * np.sin((mese_numero[m_idro] - 11) / 12 * 2 * np.pi)
    valore[m_idro] = np.clip(
        60 + stagionalita_idro + rng.normal(0, 8, m_idro.sum()),
        0, None,
    )

    # meteo (temperatura): stagionalita' annua + ciclo giorno/notte
    stagionalita_meteo = 15 * np.sin((mese_numero[m_meteo] - 4) / 12 * 2 * np.pi)
    ciclo_giorno = 4 * np.sin((ora_del_giorno[m_meteo] - 6) / 24 * 2 * np.pi)
    valore[m_meteo] = (
        18 + stagionalita_meteo + ciclo_giorno + rng.normal(0, 2, m_meteo.sum())
    ).round(1)

    # qualita' aria (PM10-like): peggiora d'inverno e nelle ore di punta
    stagionalita_aria = 25 * np.cos((mese_numero[m_aria] - 1) / 12 * 2 * np.pi)
    punta_traffico = np.where(
        np.isin(ora_del_giorno[m_aria], [7, 8, 9, 18, 19, 20]), 15, 0
    )
    valore[m_aria] = np.clip(
        35 + stagionalita_aria + punta_traffico + rng.normal(0, 10, m_aria.sum()),
        3, None,
    )

    valore = valore.round(2)
    unita = np.vectorize(UNITA_PER_TIPO.get)(tipo)

    # --- qualita' della lettura --------------------------------------------------
    qualita = rng.choice([1, 0, 2], size=n_record, p=[0.95, 0.03, 0.02])

    # --- payload: solo sui sensori "evoluti", e non su ogni campo ogni volta ----
    batteria = rng.integers(8, 100, n_record)
    rssi = rng.integers(-95, -40, n_record)
    firmware_idx = rng.integers(0, len(FIRMWARE_POSSIBILI), n_record)
    presente_batteria = rng.random(n_record) > 0.15
    presente_rssi = rng.random(n_record) > 0.15
    presente_firmware = rng.random(n_record) > 0.60  # firmware riportato di rado

    payload = np.full(n_record, "", dtype=object)
    idx_evoluti = np.flatnonzero(evoluto)
    for i in idx_evoluti:
        campi = {}
        if presente_batteria[i]:
            campi["batteria_pct"] = int(batteria[i])
        if presente_rssi[i]:
            campi["rssi_dbm"] = int(rssi[i])
        if presente_firmware[i]:
            campi["firmware"] = FIRMWARE_POSSIBILI[firmware_idx[i]]
        payload[i] = json.dumps(campi, ensure_ascii=False) if campi else ""

    df = pd.DataFrame(
        {
            "sensor_id": sensor_id,
            "ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tipo": tipo,
            "valore": valore,
            "unita": unita,
            "lat": lat,
            "lon": lon,
            "qualita": qualita,
            "payload": payload,
        }
    )

    # ordine "realistico": per sensore e poi nel tempo (facilita l'ispezione
    # manuale; il banco di prova non deve fare assunzioni sull'ordine su disco)
    df = df.sort_values(["sensor_id", "ts"]).reset_index(drop=True)
    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n-sensori", type=int, default=200, help="numero di sensori (default 200, come da §5.5)")
    ap.add_argument("--mesi", type=int, default=12, help="periodo simulato in mesi (default 12)")
    ap.add_argument("--n-record", type=int, default=1_000_000, help="numero totale di record (default 1_000_000)")
    ap.add_argument("--seme", type=int, default=42, help="seme del generatore casuale (default 42)")
    ap.add_argument("--out", type=str, default="letture.csv", help="file CSV di output")
    args = ap.parse_args()

    df = genera_letture(args.n_record, args.n_sensori, args.mesi, args.seme)
    df.to_csv(args.out, index=False)

    print(f"Generati {len(df):,} record su {args.n_sensori} sensori, {args.mesi} mesi, seme={args.seme}")
    print(f"Scritto in: {args.out}")
    print("\nControllo di correttezza (Q0 - da ripetere identico sui tre store dopo il caricamento):")
    print(f"  conteggio totale : {len(df)}")
    print(f"  somma di 'valore': {df['valore'].sum():.4f}")
    print(f"  distinct sensor_id: {df['sensor_id'].nunique()}")


if __name__ == "__main__":
    main()
