SELECT tipo,
       avg(valore) FILTER (WHERE ts >= '2024-01-01' AND ts < '2024-02-01') AS gennaio,
       avg(valore) FILTER (WHERE ts >= '2024-07-01' AND ts < '2024-08-01') AS luglio
FROM :t
WHERE (ts >= '2024-01-01' AND ts < '2024-02-01') OR (ts >= '2024-07-01' AND ts < '2024-08-01')
GROUP BY tipo ORDER BY tipo;
