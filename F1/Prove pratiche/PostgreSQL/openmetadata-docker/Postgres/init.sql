CREATE SCHEMA IF NOT EXISTS testmisurazioni;

CREATE TABLE testmisurazioni.datisintetici (
    id          bigserial,
    ts          timestamptz NOT NULL,
    categoria   text NOT NULL,
    valore      numeric NOT NULL
);

INSERT INTO testmisurazioni.datisintetici (ts, categoria, valore)
SELECT * FROM (
    SELECT
        timestamptz '2025-01-01' + (random() * interval '180 days') AS ts,
        (ARRAY['categoria_a','categoria_b','categoria_c'])[floor(random()*3+1)] AS categoria,
        random()*1000 AS valore
    FROM generate_series(1, 250000)
) sub
ORDER BY ts;

ANALYZE testmisurazioni.datisintetici;

CREATE USER openmetadata_user WITH PASSWORD 'openmetadata_pwd';
GRANT USAGE ON SCHEMA testmisurazioni TO openmetadata_user;
GRANT SELECT ON ALL TABLES IN SCHEMA testmisurazioni TO openmetadata_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA testmisurazioni GRANT SELECT ON TABLES TO openmetadata_user;
