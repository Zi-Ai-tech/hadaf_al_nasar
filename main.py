#!/usr/bin/env python
"""
Main entry point for Hadaf Al Nasar application
"""
import os
import sys

# Add the current directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from app import create_app

app = create_app()

if __name__ == "__main__":
    print("Starting Hadaf Al Nasar Application...")
    print(f"Debug mode: {app.debug}")
    print(f"Running on: http://127.0.0.1:5000")
    print("Press Ctrl+C to stop")
    print("-" * 50)
    
    # List routes
    with app.app_context():
        print("Registered routes:")
        for rule in app.url_map.iter_rules():
            if rule.endpoint != 'static':
                print(f"  {rule.rule} -> {rule.endpoint}")
    
    app.run(host='127.0.0.1', port=5000, debug=True)