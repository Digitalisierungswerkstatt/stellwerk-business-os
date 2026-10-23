import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEMO_DB_PATH = os.path.join(BASE_DIR, 'data', 'demo.db')

if not os.path.exists(DEMO_DB_PATH):
    print(f"Demo-DB nicht gefunden: {DEMO_DB_PATH}")
    print("Zuerst: python seed_demo_data.py")
    sys.exit(1)

os.environ['STELLWERK_DB_PATH'] = DEMO_DB_PATH

from app import app

print(f"\n--- Stellwerk DEMO ---")
print(f"DB:   {DEMO_DB_PATH}")
print(f"URL:  http://localhost:5001")
print(f"----------------------\n")

app.run(host=os.environ.get('STELLWERK_HOST', '127.0.0.1'),
        debug=os.environ.get('STELLWERK_DEBUG') == '1', port=5001)
