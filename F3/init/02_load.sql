-- ---------------------------------------------------------------------
-- Taglia 1M: caricamento grezzo in staging
-- ---------------------------------------------------------------------
\copy iot.staging_1m(sensor_id, ts, tipo, valore, unita, lat, lon, qualita, payload) FROM '/docker-entrypoint-initdb.d/letture_1M.csv' WITH CSV HEADER;

INSERT INTO iot.letture_1m (sensor_id, ts, tipo, valore, unita, lat, lon, qualita, payload)
SELECT sensor_id, ts, tipo, valore, unita, lat, lon, qualita, NULLIF(payload, '')::jsonb
FROM iot.staging_1m
ORDER BY ts;

DROP TABLE iot.staging_1m;

CREATE INDEX idx_letture_1m_btree ON iot.letture_1m (sensor_id, ts DESC);
CREATE INDEX idx_letture_1m_brin ON iot.letture_1m USING brin (ts);

ANALYZE iot.letture_1m;

-- ---------------------------------------------------------------------
-- Taglia 10M: caricamento grezzo in staging
-- ---------------------------------------------------------------------
\copy iot.staging_10m(sensor_id, ts, tipo, valore, unita, lat, lon, qualita, payload) FROM '/docker-entrypoint-initdb.d/letture_10M.csv' WITH CSV HEADER;

INSERT INTO iot.letture_10m (sensor_id, ts, tipo, valore, unita, lat, lon, qualita, payload)
SELECT sensor_id, ts, tipo, valore, unita, lat, lon, qualita, NULLIF(payload, '')::jsonb
FROM iot.staging_10m
ORDER BY ts;

DROP TABLE iot.staging_10m;

CREATE INDEX idx_letture_10m_btree ON iot.letture_10m (sensor_id, ts DESC);
CREATE INDEX idx_letture_10m_brin ON iot.letture_10m USING brin (ts);

ANALYZE iot.letture_10m;