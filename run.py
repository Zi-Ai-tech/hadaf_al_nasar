#!/usr/bin/env python
"""
Runner script for Hadaf Al Nasar application
"""
import os
import sys
import subprocess

def main():
    print("Starting Hadaf Al Nasar Application...")
    print("-" * 50)
    
    # Clear cache
    print("Cleaning Python cache...")
    for root, dirs, files in os.walk('.'):
        if '__pycache__' in dirs:
            pycache = os.path.join(root, '__pycache__')
            try:
                import shutil
                shutil.rmtree(pycache)
                print(f"  Cleaned: {pycache}")
            except:
                pass
        
        for file in files:
            if file.endswith('.pyc'):
                try:
                    os.remove(os.path.join(root, file))
                except:
                    pass
    
    print("-" * 50)
    print("Starting application...")
    print("Open: http://localhost:5000")
    print("Login: http://localhost:5000/login")
    print("Press Ctrl+C to stop")
    print("-" * 50)
    
    # Run the app
    os.environ['FLASK_APP'] = 'wsgi.py'
    os.environ['FLASK_DEBUG'] = '1'
    
    try:
        subprocess.run(['flask', 'run', '--debug'])
    except KeyboardInterrupt:
        print("
Application stopped.")
    except Exception as e:
        print(f"Error: {e}")
        print("
Trying alternative method...")
        
        # Try running directly
        try:
            from app import create_app
            app = create_app()
            app.run(debug=True, host='127.0.0.1', port=5000)
        except Exception as e2:
            print(f"Failed to start: {e2}")
            input("Press Enter to exit...")

if __name__ == '__main__':
    main()