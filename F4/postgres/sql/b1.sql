SELECT date_trunc('hour', ts) AS ora, avg(valore) AS media FROM :t WHERE tipo = 'idrometrico' AND ts >= :'rif'::timestamptz - interval '6 months' GROUP BY 1 ORDER BY 1;
