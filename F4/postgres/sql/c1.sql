-- 100 INSERT separate (autocommit = un commit ciascuna)
SELECT 'INSERT INTO iot.letture_c1 (sensor_id, ts, tipo, valore, unita, lat, lon, qualita, payload) SELECT sensor_id, ts, tipo, valore, unita, lat, lon, qualita, payload FROM iot.c1_batch'
FROM generate_series(1, 100) \gexec
