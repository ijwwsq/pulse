#!/usr/bin/env bash
set -euo pipefail

echo "[1/3] Starting PostgreSQL container and running DB init scripts..."
docker compose up -d postgres

echo "[2/3] Installing Python dependencies..."
pip install -r requirements.txt

echo "[3/3] Done. Export DATABASE_URL and run API:"
echo "export DATABASE_URL=\"postgresql://postgres:postgres@localhost:5432/pulse\""
echo "uvicorn app.main:app --reload"
