SELECT count(*) AS totale, count(payload->>'batteria_pct') AS con_campo, avg((payload->>'batteria_pct')::numeric) AS media_batteria FROM :t;
