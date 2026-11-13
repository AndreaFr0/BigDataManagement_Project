SELECT 'residue=' || count(*) || '; dimensione=' || pg_size_pretty(pg_total_relation_size('iot.letture_c4')) FROM iot.letture_c4 WHERE sensor_id = 'S-042';
