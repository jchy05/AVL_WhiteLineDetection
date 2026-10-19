"""Portable entry point for the original, unchanged frame-by-frame detector."""
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
try:
    from avl_white_lines.original_viewer import main
except ImportError as exc:
    raise SystemExit(f'Missing dependency: {exc}. Install with: python -m pip install -e ".[desktop]"') from exc

if __name__=='__main__': main()
