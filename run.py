import sys
import os

# Ensures all packages resolve correctly regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app

if __name__ == "__main__":
    print("SkyRoute Planner running at http://localhost:5000")
    app.run(debug=True, port=5000)