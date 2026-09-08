-- =====================================================================
-- Setup: creazione dello schema e della tabella
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS testmisurazioni;

CREATE TABLE testmisurazioni.datisintetici (
    id          bigserial,
    ts          timestamptz NOT NULL,
    categoria   text NOT NULL,
    valore      numeric NOT NULL
);

-- INSERIMENTO DATI
INSERT INTO testmisurazioni.datisintetici (ts, categoria, valore)
SELECT * FROM (
    SELECT
        timestamptz '2025-01-01' + (random() * interval '180 days') AS ts,
        (ARRAY['categoria_a','categoria_b','categoria_c'])[floor(random()*3+1)] AS categoria,
        random()*1000 AS valore
    FROM generate_series(1, 250000)
) sub
ORDER BY ts;

-- Mostra in formato tabellare
\d testmisurazioni.datisintetici

-- Verifica che effettivamente ci sono 250.000 righe
SELECT count(*) FROM testmisurazioni.datisintetici;


-- =====================================================================
-- EXPLAIN ed EXPLAIN ANALYZE
-- =====================================================================

-- Mostra la decisione che il pianificatore intende attuare
EXPLAIN SELECT * FROM testmisurazioni.datisintetici WHERE categoria = 'categoria_b';

-- Mostra ed esegue la decisione del pianificatore
EXPLAIN ANALYZE SELECT * FROM testmisurazioni.datisintetici WHERE categoria = 'categoria_b';

-- Disabilitiamo temporanemente la parallelizzazione
SET max_parallel_workers_per_gather = 0;

EXPLAIN ANALYZE SELECT * FROM testmisurazioni.datisintetici WHERE categoria = 'categoria_b' ORDER BY ts DESC LIMIT 1;

-- Ripristiniamo la parallelizzazione
RESET max_parallel_workers_per_gather;

EXPLAIN ANALYZE SELECT categoria, avg(valore) FROM testmisurazioni.datisintetici GROUP BY categoria;


-- =====================================================================
-- Indice B-tree
-- =====================================================================

-- Creazione dell'indice
CREATE INDEX idx_datisintetici_btree
    ON testmisurazioni.datisintetici (categoria, ts DESC);

-- Mostra lo spazio occupato in memoria dall'indice B-Tree
SELECT pg_size_pretty(pg_relation_size('testmisurazioni.idx_datisintetici_btree'))
    AS dimensione_btree;

EXPLAIN ANALYZE SELECT * FROM testmisurazioni.datisintetici WHERE categoria = 'categoria_b' ORDER BY ts DESC LIMIT 1;


-- =====================================================================
-- Indice BRIN
-- =====================================================================

-- Creazione dell'indice
CREATE INDEX idx_datisintetici_brin
    ON testmisurazioni.datisintetici USING brin (ts);

-- Mostra lo spazio occupato in memoria dall'indice BRIN
SELECT pg_size_pretty(pg_relation_size('testmisurazioni.idx_datisintetici_brin'))
    AS dimensione_brin;

EXPLAIN ANALYZE SELECT categoria, avg(valore) FROM testmisurazioni.datisintetici WHERE ts >= '2025-02-01' AND ts < '2025-03-01' GROUP BY categoria;


-- =====================================================================
-- Partizionamento dichiarativo
-- =====================================================================

-- Rinominiamo la tabella e ne creiamo una nuova vuota
ALTER TABLE testmisurazioni.datisintetici RENAME TO datisintetici_old;

CREATE TABLE testmisurazioni.datisintetici (
    id          bigserial,
    ts          timestamptz NOT NULL,
    categoria   text NOT NULL,
    valore      numeric NOT NULL
) PARTITION BY RANGE (ts);

-- Generazione tramite scripting delle partizioni
DO $$
DECLARE
    mese date;
BEGIN
    FOR mese IN SELECT generate_series('2025-01-01'::date, '2025-06-01'::date, '1 month') LOOP
        EXECUTE format(
            'CREATE TABLE testmisurazioni.datisintetici_%s PARTITION OF testmisurazioni.datisintetici FOR VALUES FROM (%L) TO (%L)',
            to_char(mese, 'YYYY_MM'),
            mese,
            mese + interval '1 month'
        );
    END LOOP;
END $$;

\dt testmisurazioni.datisintetici_2025*

-- Inseriamo nella tabella i valori precedentemente inseriti
INSERT INTO testmisurazioni.datisintetici SELECT * FROM testmisurazioni.datisintetici_old ORDER BY ts;

SELECT count(*) FROM testmisurazioni.datisintetici;
SELECT count(*) FROM testmisurazioni.datisintetici_old;

-- Gli indici definiti per la tabella padre vengono ereditati dalle partizioni
CREATE INDEX idx_datisintetici_brin ON testmisurazioni.datisintetici USING brin (ts);
CREATE INDEX idx_datisintetici_btree ON testmisurazioni.datisintetici (categoria, ts DESC);

EXPLAIN ANALYZE SELECT categoria, avg(valore) FROM testmisurazioni.datisintetici WHERE ts >= '2025-02-01' AND ts < '2025-03-01' GROUP BY categoria;

EXPLAIN ANALYZE SELECT categoria, avg(valore) FROM testmisurazioni.datisintetici WHERE ts >= '2025-01-15' AND ts < '2025-03-15' GROUP BY categoria;

-- Per la rimozione della vecchia tabella
-- DROP TABLE testmisurazioni.datisintetici_old;
