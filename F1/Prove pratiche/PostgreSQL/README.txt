DISPOSIZIONE DEI FILE:

PROVE PRATICHE CON POSTGRES
- postgres_setup.sh contiene le istruzioni per effettuare il pulling dell'immagine postgres, creare il container ed eseguire psql al suo interno.
- postgre.sql contiene le istruzioni utilizzate per le prove pratiche.

PROVE PRATICHE CON OPENMETADATA
- openmetadata-docker/OpenMetadata_Postgres.pdf è la guida contenente i comandi applicati
- openmetadata-docker/docker-compose.yml contiene le istruzioni per l'installazione di OpenMetadata (https://docs.open-metadata.org/v2.0.x/quick-start/local-docker-deployment)
- openmetadata-docker/setup_openmetadata.sh esporta delle delle variabili d'ambiente per 
  garantire che venga utilizzata la versione 2.0.1 ed esegue il docker-compose.yml (https://docs.open-metadata.org/v2.0.x/quick-start/local-docker-deployment)
- openmetadata-docker/Postgres/docker-compose.yml crea un containere Postgres e specifica la rete tramite cui ricevere i dati.
- openmetadata-docker/start.sh è lo script che fa partire tutti i container automaticaments.

Eseguendo start.sh avviene la creazione dei container, pertanto si possono effettuare i test riportati nel pdf OpenMetadata_Postgress.
Al termine dei test è necessario mandare in stop i container.