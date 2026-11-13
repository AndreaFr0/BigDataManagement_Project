DROP TABLE IF EXISTS iot.letture_c1;
CREATE TABLE iot.letture_c1 (
    id bigserial, sensor_id text NOT NULL, ts timestamptz NOT NULL, tipo text NOT NULL,
    valore double precision NOT NULL, unita text NOT NULL, lat double precision,
    lon double precision, qualita integer, payload jsonb
) PARTITION BY RANGE (ts);
DO $$
BEGIN
  FOR m IN 1..12 LOOP
    EXECUTE format('CREATE TABLE iot.letture_c1_%s PARTITION OF iot.letture_c1 FOR VALUES FROM (%L) TO (%L)',
                   lpad(m::text, 2, '0'), make_date(2024, m, 1), (make_date(2024, m, 1) + interval '1 month')::date);
  END LOOP;
END $$;
CREATE INDEX ON iot.letture_c1 (sensor_id, ts DESC);
CREATE INDEX ON iot.letture_c1 USING brin (ts);

-- batch deterministico di 10.000 letture, ordinate per ts
DROP TABLE IF EXISTS iot.c1_batch;
CREATE TABLE iot.c1_batch AS
SELECT 'S-' || lpad((1 + (i * 37) % 200)::text, 3, '0') AS sensor_id,
       timestamptz '2024-01-01 00:00:00+00' + i * interval '50 minutes' AS ts,
       (ARRAY['idrometrico','meteo','qualita_aria'])[1 + i % 3] AS tipo,
       ((i * 7919) % 10000) / 100.0 AS valore,
       (ARRAY['cm','°C','µg/m³'])[1 + i % 3] AS unita,
       40.35::double precision AS lat, 18.17::double precision AS lon,
       1 AS qualita, NULL::jsonb AS payload
FROM generate_series(0, 9999) AS i;
