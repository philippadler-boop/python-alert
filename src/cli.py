"""CLI entry point for the alert tool."""
import sys
from pathlib import Path

# Add root directory to path so main.py can be imported
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from main import main

if __name__ == "__main__":
    main()
