#!/bin/bash
set -e

echo "Running database migrations..."
flask db upgrade

echo "Starting Gunicorn..."
gunicorn main:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120