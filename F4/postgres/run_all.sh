#!/bin/bash
# Banco di prova PostgreSQL: esegue sql/*.sql, salva i tempi in iot.risultati_tentativi,
# li sintetizza in iot.risultati ed esporta risultati_finali.csv (+ risultati.csv con i tentativi).
# Protocollo: 3 esecuzioni; la prima e' "a freddo", delle altre due si fa la mediana.
# Tempo = quello misurato da psql (\timing: wall clock lato client, incluso il trasferimento dei risultati).
#
# Uso:  ./run_all.sh
# Connessione: variabili PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE (default: localhost:5432 admin/postgres progetto_db).
# Se psql non e' installato sull'host usa  docker exec -i pg-progetto psql  (container: PGCONTAINER).
set -euo pipefail
cd "$(dirname "$0")"

export PGHOST=${PGHOST:-localhost} PGPORT=${PGPORT:-5432} PGUSER=${PGUSER:-admin}
export PGPASSWORD=${PGPASSWORD:-postgres} PGDATABASE=${PGDATABASE:-progetto_db}
export PGOPTIONS="${PGOPTIONS:--c client_min_messages=warning}"
if [ -z "${PSQL:-}" ]; then
  if command -v psql >/dev/null 2>&1; then PSQL="psql"
  else PSQL="docker exec -i ${PGCONTAINER:-pg-progetto} psql -U $PGUSER -d $PGDATABASE"; fi
fi
PSQL="$PSQL -X -q -A -t -v ON_ERROR_STOP=1"
RIPETIZIONI=3
TAGLIE=("1m iot.letture_1m" "10m iot.letture_10m")
TAB=""; RIF=""

# esegue un file SQL (con tempo); variabili: :t = tabella, :'rif' = max(ts)
con_tempo()   { { echo '\timing on'; cat "$1"; } | $PSQL -v t="$TAB" -v rif="$RIF"; }
senza_tempo() { $PSQL -v t="$TAB" -v rif="$RIF" < "$1"; }

registra() {  # prova dettaglio taglia tentativo tempo nota
  local nota=${6//\'/\'\'}
  printf "INSERT INTO iot.risultati_tentativi (prova,dettaglio,taglia,tentativo,tempo_ms,nota) VALUES ('%s','%s','%s',%s,%s,'%s');\n" \
    "$1" "$2" "$3" "$4" "${5:-NULL}" "$nota" | $PSQL
}

passo() {  # prova taglia tentativo dettaglio file
  local out ms nota
  out=$(con_tempo "sql/$5.sql")
  ms=$(printf '%s' "$out" | awk '/^Time: /{s+=$2} END{printf "%.3f", s}')
  if [ -f "sql/$5.nota.sql" ]; then
    nota=$(senza_tempo "sql/$5.nota.sql" | paste -sd';' -)
  else
    nota="righe=$(printf '%s' "$out" | awk '!/^Time: /{n++} END{print n+0}')"
  fi
  registra "$1" "$4" "$2" "$3" "$ms" "$nota"
  echo "  $1 $2 ${4:+$4 }tentativo $3: $ms ms ($nota)"
}

prova() {  # prova taglia tabella prepara|- passo...   (passo = "dettaglio:file")
  local P=$1 T=$2 PREP=$4 k s; TAB=$3
  RIF=$(echo "SELECT max(ts) FROM $TAB" | $PSQL)
  shift 4
  for k in $(seq 1 "$RIPETIZIONI"); do
    if [ "$PREP" != "-" ]; then senza_tempo "sql/$PREP.sql" >/dev/null; fi
    for s in "$@"; do passo "$P" "$T" "$k" "${s%%:*}" "${s#*:}"; done
  done
}

osserva() {  # prova taglia tabella file  (nessun tempo, solo nota)
  TAB=$3; RIF=""
  registra "$1" "" "$2" 1 "" "$(senza_tempo "sql/$4.sql" | paste -sd';' -)"
  echo "  $1 $2: osservazione registrata"
}

$PSQL < sql/00_risultati.sql >/dev/null

# stesso ordine per tutte le prove (e per gli altri store)
for q in q0 a1 a2 a3 b1 b2 b3 b4; do
  echo "== ${q^^}"
  for e in "${TAGLIE[@]}"; do set -- $e; prova "${q^^}" "$1" "$2" - ":$q"; done
done

echo "== C1"; prova C1 10000x100 iot.letture_1m c1_prepara ":c1"
echo "== C2"; prova C2 1m iot.letture_1m c2_prepara "campo_aggiunto:c2_aggiungi" "campo_rinominato:c2_rinomina" "tipo_promosso:c2_promuovi"
echo "== C3"; osserva C3 - iot.letture_1m c3
echo "== C4"; prova C4 1m iot.letture_1m c4_prepara "delete:c4_delete" "vacuum_full:c4_vacuum"
echo "== C5"; for e in "${TAGLIE[@]}"; do set -- $e; prova C5 "$1" "$2" - ":c5"; done
for o in o1 o3; do
  echo "== ${o^^}"
  for e in "${TAGLIE[@]}"; do set -- $e; osserva "${o^^}" "$1" "$2" "$o"; done
done

# sintesi in iot.risultati ed export CSV
$PSQL < sql/finale.sql >/dev/null
echo "COPY (SELECT prova,NULLIF(dettaglio,'') AS dettaglio,store,taglia,tempo_prima_ms,tempo_mediana_ms,nota FROM iot.risultati ORDER BY ord) TO STDOUT WITH CSV HEADER" | $PSQL > risultati_finali.csv
echo "COPY (SELECT prova,NULLIF(dettaglio,'') AS dettaglio,store,taglia,tentativo,tempo_ms,nota FROM iot.risultati_tentativi ORDER BY id) TO STDOUT WITH CSV HEADER" | $PSQL > risultati.csv
echo; echo "Fatto: risultati_finali.csv (sintesi) e risultati.csv (tentativi); tabelle iot.risultati / iot.risultati_tentativi"
