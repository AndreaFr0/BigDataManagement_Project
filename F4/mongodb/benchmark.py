
#!/usr/bin/env python3

import csv
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
QUERY_DIR = BASE_DIR / "Scripts"
TIME_DIR = BASE_DIR / "tempi_esecuzione"
RESULT_DIR = BASE_DIR / "risultati"

MONGODB_URI = os.environ.get(
    "MONGODB_URI",
    "mongodb://admin:admin_password@localhost:27017/progetto_db?authSource=admin"
)

MONGO_CONTAINER = "mongo"


def execute_query(query_file: Path):
    """Esegue la query tramite mongosh nel container Docker."""

    start = time.perf_counter()

    container_query_path = f"/tmp/{query_file.name}"

    # Copia il file JS nel container
    subprocess.run(
        [
            "docker",
            "cp",
            str(query_file),
            f"{MONGO_CONTAINER}:{container_query_path}"
        ],
        check=True,
        capture_output=True,
        text=True
    )

    # Esegue mongosh all'interno del container
    process = subprocess.run(
        [
            "docker",
            "exec",
            MONGO_CONTAINER,
            "mongosh",
            MONGODB_URI,
            "--quiet",
            "--file",
            container_query_path
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    elapsed = time.perf_counter() - start

    if process.returncode != 0:
        raise RuntimeError(
            f"Errore nell'esecuzione:\n{process.stderr}"
        )

    return elapsed, process.stdout
    

def save_result(query_file: Path, output: str):
    """Salva l'output della query in un CSV."""

    output_file = RESULT_DIR / f"{query_file.stem}.csv"

    with output_file.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as csv_file:

        writer = csv.writer(csv_file)

        writer.writerow(["output_mongosh"])
        writer.writerow([output])

    print(f"Risultato salvato: {output_file.name}")


def main():

    if not QUERY_DIR.is_dir():
        print(f"Cartella non trovata: {QUERY_DIR}")
        sys.exit(1)

    query_files = sorted(
    	QUERY_DIR.glob("*.js"),
    	key=lambda f: (
        	0 if f.name == "q0_controllo_1M.js" else
        	1 if f.name == "q0_controllo_10M.js" else
        	2,
        	f.name.lower()
    	)
	)

    if not query_files:
        print("Nessuna query trovata.")
        return

    TIME_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    timing_file = TIME_DIR / "tempi.csv"

    errors = []

    with timing_file.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as csv_file:

        writer = csv.writer(csv_file)

        writer.writerow([
            "query",
            "prima_esecuzione_secondi",
            "seconda_esecuzione_secondi",
            "terza_esecuzione_secondi",
            "mediana_seconda_terza_secondi"
        ])

        for query_file in query_files:

            print(f"\nQuery: {query_file.name}")

            try:
                # Prima esecuzione: conserviamo l'output
                time1, first_output = execute_query(query_file)

                # Seconda esecuzione
                time2, _ = execute_query(query_file)

                # Terza esecuzione
                time3, _ = execute_query(query_file)

                # Mediana degli ultimi due tempi
                median_time = statistics.median([time2, time3])

                writer.writerow([
                    query_file.name,
                    f"{time1:.6f}",
                    f"{time2:.6f}",
                    f"{time3:.6f}",
                    f"{median_time:.6f}"
                ])

                csv_file.flush()

                # Salvataggio output della prima esecuzione
                save_result(query_file, first_output)

                print(f"Prima esecuzione: {time1:.6f} s")
                print(f"Seconda esecuzione: {time2:.6f} s")
                print(f"Terza esecuzione: {time3:.6f} s")
                print(f"Mediana: {median_time:.6f} s")

            except Exception as exc:

                errors.append(f"{query_file.name}: {exc}")

                print(f"ERRORE: {exc}")

    print("\nBenchmark completato.")
    print(f"Tempi: {timing_file}")
    print(f"Risultati: {RESULT_DIR}")

    if errors:
        print("\nQuery non completate:")

        for error in errors:
            print(error)

        sys.exit(1)


if __name__ == "__main__":
    main()
