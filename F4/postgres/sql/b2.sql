-- soglia 90 cm: DEVE essere identica sui tre store
SELECT sensor_id, count(*) AS n FROM :t WHERE tipo = 'idrometrico' AND valore > 90 GROUP BY sensor_id ORDER BY n DESC, sensor_id LIMIT 10;
