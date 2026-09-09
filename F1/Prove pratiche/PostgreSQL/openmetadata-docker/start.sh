#!/bin/bash

#Creazione della rete condivisa per i due compose: OpenMetadata e PostgreSQL
echo "Creazione della rete condivisa"
docker network create rete_pg

#Esportazione delle variabili d'ambiente necessarie ad OpenMetadata (richiesto dalla guida ufficiale)
echo "Esportando le variabili d'ambiente necessarie'"
export OPENMETADATA_DB_IMAGE=docker.getcollate.io/openmetadata/db:2.0.1
export OPENMETADATA_SERVER_IMAGE=docker.getcollate.io/openmetadata/server:2.0.1
export OPENMETADATA_INGESTION_IMAGE=docker.getcollate.io/openmetadata/ingestion:2.0.1

#Avvio del compose di PostgreSQL
cd ./Postgres
echo "Avvio di Postgres"
docker compose -f docker-compose.yml up --detach 

#Avvio del compose di OpenMetadata
cd ..
echo "Avvio di OpenMetadata"
docker compose -f docker-compose.yml up --detach