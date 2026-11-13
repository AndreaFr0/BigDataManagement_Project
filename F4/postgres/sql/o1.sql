SELECT 'dati ' || pg_size_pretty(sum(pg_table_size(inhrelid)))
    || '; indici ' || pg_size_pretty(sum(pg_indexes_size(inhrelid)))
    || '; totale ' || pg_size_pretty(sum(pg_total_relation_size(inhrelid)))
FROM pg_inherits WHERE inhparent = :'t'::regclass;
