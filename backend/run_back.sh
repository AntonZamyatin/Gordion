#!/bin/bash
source /home/enzo/miniforge3/bin/activate
conda activate gordion
uvicorn app.main:app --reload --port 8000
