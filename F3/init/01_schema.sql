CREATE SCHEMA IF NOT EXISTS iot;

-- ---------------------------------------------------------------------
-- Generazione delle 12 partizioni mensili per una tabella
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION iot.crea_partizioni_mensili(nome_tabella text)
RETURNS void AS $$
DECLARE
    mese date;
BEGIN
    FOR mese IN SELECT generate_series('2024-01-01'::date, '2024-12-01'::date, '1 month') LOOP
        EXECUTE format(
            'CREATE TABLE iot.%I PARTITION OF iot.%I FOR VALUES FROM (%L) TO (%L)',
            nome_tabella || '_' || to_char(mese, 'YYYY_MM'),
            nome_tabella,
            mese,
            mese + interval '1 month'
        );
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------
-- Tabella taglia 1M
-- ---------------------------------------------------------------------
CREATE TABLE iot.letture_1m (
    id          bigserial,
    sensor_id   text NOT NULL,
    ts          timestamptz NOT NULL,
    tipo        text NOT NULL CHECK (tipo IN ('idrometrico','meteo','qualita_aria')),
    valore      double precision NOT NULL,
    unita       text NOT NULL,
    lat         double precision,
    lon         double precision,
    qualita     integer,
    payload     jsonb
) PARTITION BY RANGE (ts);

SELECT iot.crea_partizioni_mensili('letture_1m');

-- ---------------------------------------------------------------------
-- Tabella taglia 10M
-- ---------------------------------------------------------------------
CREATE TABLE iot.letture_10m (
    id          bigserial,
    sensor_id   text NOT NULL,
    ts          timestamptz NOT NULL,
    tipo        text NOT NULL CHECK (tipo IN ('idrometrico','meteo','qualita_aria')),
    valore      double precision NOT NULL,
    unita       text NOT NULL,
    lat         double precision,
    lon         double precision,
    qualita     integer,
    payload     jsonb
) PARTITION BY RANGE (ts);

SELECT iot.crea_partizioni_mensili('letture_10m');

-- ---------------------------------------------------------------------
-- Tabelle di staging (una per taglia, non partizionate, per il caricamento grezzo)
-- ---------------------------------------------------------------------
CREATE TABLE iot.staging_1m (
    sensor_id   text,
    ts          timestamptz,
    tipo        text,
    valore      double precision,
    unita       text,
    lat         double precision,
    lon         double precision,
    qualita     integer,
    payload     text
);

CREATE TABLE iot.staging_10m (
    sensor_id   text,
    ts          timestamptz,
    tipo        text,
    valore      double precision,
    unita       text,
    lat         double precision,
    lon         double precision,
    qualita     integer,
    payload     text
);