SELECT CASE WHEN current_setting('archive_mode') = 'off'
            THEN 'non applicabile: nessun time travel nativo, PITR non configurato'
            ELSE 'possibile solo via PITR (backup base + archivio WAL), non via query' END
       || ' [wal_level=' || current_setting('wal_level')
       || ', archive_mode=' || current_setting('archive_mode') || ']';
