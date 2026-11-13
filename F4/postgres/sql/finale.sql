-- prima esecuzione ("a freddo") e mediana delle successive (2 e 3)
TRUNCATE iot.risultati;
INSERT INTO iot.risultati (ord, prova, dettaglio, store, taglia, tempo_prima_ms, tempo_mediana_ms, nota)
SELECT min(id), prova, dettaglio, store, taglia,
       round(max(tempo_ms) FILTER (WHERE tentativo = 1), 3),
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY tempo_ms)
              FILTER (WHERE tentativo > 1))::numeric, 3),
       (array_agg(nota ORDER BY tentativo DESC))[1]
FROM iot.risultati_tentativi
GROUP BY prova, dettaglio, store, taglia;
