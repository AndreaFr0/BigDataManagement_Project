DROP TABLE IF EXISTS iot.letture_c4;
CREATE TABLE iot.letture_c4 AS SELECT * FROM :t;
CREATE INDEX ON iot.letture_c4 (sensor_id, ts DESC);
CREATE INDEX ON iot.letture_c4 USING brin (ts);
