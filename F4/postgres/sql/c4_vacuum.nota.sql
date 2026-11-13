SELECT 'dimensione dopo vacuum full=' || pg_size_pretty(pg_total_relation_size('iot.letture_c4'));
