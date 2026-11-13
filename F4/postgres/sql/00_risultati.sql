CREATE SCHEMA IF NOT EXISTS iot;
DROP TABLE IF EXISTS iot.risultati_tentativi, iot.risultati;

-- un tentativo per riga (dati grezzi)
CREATE TABLE iot.risultati_tentativi (
    id        serial PRIMARY KEY,
    prova     text NOT NULL,
    dettaglio text NOT NULL DEFAULT '',
    store     text NOT NULL DEFAULT 'postgres',
    taglia    text NOT NULL,
    tentativo int  NOT NULL,
    tempo_ms  numeric(14,3),
    nota      text
);

-- una riga per prova/taglia: stesso formato del CSV finale
CREATE TABLE iot.risultati (
    ord              int,
    prova            text,
    dettaglio        text,
    store            text,
    taglia           text,
    tempo_prima_ms   numeric(14,3),
    tempo_mediana_ms numeric(14,3),
    nota             text
);
