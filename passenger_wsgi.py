import sys
import os

# Add your app directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import your Flask application
from app import app as application  # Replace 'application' with your main file name