SELECT count(*), sum(valore), count(DISTINCT sensor_id) FROM :t;
