# C:\Users\PC\hadaf_al_nasar\clear_cache.py
import os
import shutil
import sys

print("Cleaning Python cache files...")

def clean_pycache(root_dir):
    for root, dirs, files in os.walk(root_dir):
        # Remove __pycache__ directories
        if '__pycache__' in dirs:
            pycache_path = os.path.join(root, '__pycache__')
            print(f"Removing: {pycache_path}")
            shutil.rmtree(pycache_path)
            dirs.remove('__pycache__')  # Don't walk into removed dir
        
        # Remove .pyc files
        for file in files:
            if file.endswith('.pyc'):
                pyc_path = os.path.join(root, file)
                print(f"Removing: {pyc_path}")
                os.remove(pyc_path)

# Clean the entire project directory
project_root = os.path.dirname(os.path.abspath(__file__))
clean_pycache(project_root)

print("\n✓ Cache cleared. Restarting Flask app...")

# Also clean the venv cache if exists
venv_path = os.path.join(project_root, 'venv')
if os.path.exists(venv_path):
    clean_pycache(venv_path)
    print("✓ Cleaned venv cache")

print("\nNow restart Flask with: flask run --debug")