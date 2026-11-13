SELECT * FROM :t WHERE sensor_id = 'S-042' AND ts >= :'rif'::timestamptz - interval '24 hours' ORDER BY ts;
