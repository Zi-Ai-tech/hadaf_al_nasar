# clear_pycache.py
import os
import shutil

print("=== Clearing Python Cache ===")

pycache_dirs = []

# Find all __pycache__ directories
for root, dirs, files in os.walk('.'):
    if '__pycache__' in dirs:
        pycache_path = os.path.join(root, '__pycache__')
        pycache_dirs.append(pycache_path)

print(f"Found {len(pycache_dirs)} __pycache__ directories")

for pycache_dir in pycache_dirs:
    try:
        shutil.rmtree(pycache_dir)
        print(f"✅ Removed: {pycache_dir}")
    except Exception as e:
        print(f"❌ Error removing {pycache_dir}: {e}")

print("\n=== Also removing .pyc files ===")

# Remove any loose .pyc files
pyc_files = []
for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.pyc'):
            pyc_path = os.path.join(root, file)
            pyc_files.append(pyc_path)

print(f"Found {len(pyc_files)} .pyc files")

for pyc_file in pyc_files:
    try:
        os.remove(pyc_file)
        print(f"✅ Removed: {pyc_file}")
    except Exception as e:
        print(f"❌ Error removing {pyc_file}: {e}")

print("\n✅ Python cache cleared!")
print("Restart your Flask app and try again.")