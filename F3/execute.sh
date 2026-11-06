#!/bin/bash
DIR_PATH='./Script_Generazione_Dati'
PROJECT_DATA="letture/data"

#Creating data Directory
mkdir -p $PROJECT_DATA

#Creating a temporary virtual environment
python3 -m venv venv
source venv/bin/activate

#Dependecies Install
pip install numpy pandas

#Command Execution
python3 $DIR_PATH/genera_dataset.py --n-sensori 200 --mesi 12 --n-record 1000000 --seme 42 --out $PROJECT_DATA/letture_1M.csv
python3 $DIR_PATH/genera_dataset.py --n-sensori 200 --mesi 12 --n-record 10000000 --seme 42 --out $PROJECT_DATA/letture_10M.csv

#Deactivating and Removing the Virtual Environment
deactivate
rm -rf venv
