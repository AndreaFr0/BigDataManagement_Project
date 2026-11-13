SELECT count(DISTINCT sensor_id) FROM :t WHERE ts >= :'rif'::timestamptz - interval '5 minutes';
