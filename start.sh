#!/bin/bash
set -e

echo "=== Creating database tables from models ==="
python -c "
from app import create_app, db
import app.models.registry as registry
app = create_app()
registry.load_models()
with app.app_context():
    db.create_all()
    print('✓ Tables created successfully')
"

echo "=== Ensuring admin user exists ==="
python -c "
from app import create_app, db
from app.models.core.user import User
app = create_app()
with app.app_context():
    if not User.query.filter_by(username='admin').first():
        u = User(
            username='admin',
            full_name='Administrator',
            user_type='admin',
            is_active=True,
            password='ChangeMe123!'
        )
        db.session.add(u)
        db.session.commit()
        print('✓ Admin user created')
        print('  Username: admin')
        print('  Password: ChangeMe123!')
    else:
        print('✓ Admin user already exists')
"

echo "=== Starting Gunicorn ==="
gunicorn main:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120