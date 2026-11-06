#!/bin/bash
echo "=== INIZIO IMPORTAZIONE CSV IN MONGODB ==="

# Importa il primo file da 1M
mongoimport --username admin \
            --password admin_password \
            --authenticationDatabase admin \
            --db progetto_db \
            --collection letture_1M \
            --type csv \
            --file /tmp/letture_1M.csv \
            --headerline

# Importa il secondo file da 10M
mongoimport --username admin \
            --password admin_password \
            --authenticationDatabase admin \
            --db progetto_db \
            --collection letture_10M \
            --type csv \
            --file /tmp/letture_10M.csv \
            --headerline

echo "=== IMPORTAZIONE MONGODB COMPLETATA ==="
echo "=== CREAZIONE INDICI ==="
mongosh --quiet \
        -u admin -p admin_password --authenticationDatabase admin \
        progetto_db --eval '
  db.letture_1M.createIndex({ sensor_id: 1, ts: -1 });
  db.letture_10M.createIndex({ sensor_id: 1, ts: -1 });
'

echo "=== IMPORTAZIONE MONGODB COMPLETATA ==="
