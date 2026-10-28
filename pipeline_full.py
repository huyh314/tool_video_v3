"""Real Gemini video analysis. Original demo is preserved under backups/."""
import sys
from tool1 import main
if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python pipeline_full.py <video.mp4>')
        raise SystemExit(2)
    raise SystemExit(main(['--analyze-file', sys.argv[1]]))
