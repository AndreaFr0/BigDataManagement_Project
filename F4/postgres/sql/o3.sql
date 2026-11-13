SELECT 'btree ' || pg_size_pretty(sum(s) FILTER (WHERE amname = 'btree'))
    || '; brin ' || pg_size_pretty(sum(s) FILTER (WHERE amname = 'brin'))
    || '; rapporto ' || round(sum(s) FILTER (WHERE amname = 'btree')::numeric
                            / sum(s) FILTER (WHERE amname = 'brin')) || 'x'
FROM (SELECT am.amname, pg_relation_size(i.indexrelid) AS s
      FROM pg_index i
      JOIN pg_class c ON c.oid = i.indexrelid
      JOIN pg_am am ON am.oid = c.relam
      JOIN pg_inherits h ON h.inhrelid = i.indrelid
      WHERE h.inhparent = :'t'::regclass AND am.amname IN ('btree', 'brin')) x;
