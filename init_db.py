from app import create_app, db
from werkzeug.security import generate_password_hash
import enum

# Define UserType enum
class UserType(enum.Enum):
    ACCOUNTS = "accounts"
    TRANSPORT = "transport"
    ADMIN = "admin"

app = create_app()

with app.app_context():
    # Create all tables
    db.create_all()
    
    # Check if admin user already exists
    from app.models import User
    if not User.query.filter_by(username='admin').first():
        # Create admin user
        admin_user = User(
            username='admin',
            password_hash=generate_password_hash('admin123'),
            user_type=UserType.ADMIN
        )
        db.session.add(admin_user)
        db.session.commit()
        print("Database initialized and admin user created!")
    else:
        print("Admin user already exists.")