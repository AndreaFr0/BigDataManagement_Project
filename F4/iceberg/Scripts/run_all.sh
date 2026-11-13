#!/usr/bin/env bash
set -euo pipefail

# Percorso della cartella contenente run_all.sh
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Percorso della cartella contenente gli script Python
SCRIPTS_DIR="$BASE_DIR/Scripts"

scripts=(
  Q0.py
  A1.py
  A2.py
  A3.py
  B1.py
  B2.py
  B3.py
  B4.py
  C1.py
  C2.py
  C3.py
  C4.py
  C5.py
  O1.py
  O2.py
  O4.py
)

for script in "${scripts[@]}"; do
  echo "========== Esecuzione: $script =========="
  python3 "$script"
  echo "========== Completato: $script =========="
done

echo "Tutti gli script sono stati eseguiti correttamente."
