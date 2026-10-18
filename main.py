"""
Entry point. Run with: uv run python main.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from agent.loop import main

if __name__ == "__main__":
    main()
