#!/bin/bash
set -e

echo "=== Creating database tables from models ==="
python -c "
from app import create_app, db
import app.models.registry as registry
app = create_app()
registry.load_models()   # ensure all models are registered
with app.app_context():
    db.create_all()
    print('✓ Tables created successfully')
"

echo "=== Starting Gunicorn ==="
gunicorn main:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120