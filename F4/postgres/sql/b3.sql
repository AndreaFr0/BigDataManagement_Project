SELECT date_trunc('month', ts) AS mese, count(DISTINCT sensor_id) AS sensori FROM :t GROUP BY 1 ORDER BY 1;
