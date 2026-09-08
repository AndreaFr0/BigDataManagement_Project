#!/bin/bash

docker pull postgres:17

docker run --name pg-progetto -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:17

docker exec -it pg-progetto psql -U postgres
