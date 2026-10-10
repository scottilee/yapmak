"""Scan generated artifacts before submission; report file names, never secret contents."""
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from artifact_security import check_artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+', type=Path)
    args = parser.parse_args()
    failed = []
    for path in args.files:
        try:
            check_artifact(path.read_text())
        except (ValueError, OSError) as error:
            failed.append(path)
            print(f'{path}: {type(error).__name__}; artifact check failed', file=sys.stderr)
    if failed:
        raise SystemExit(1)
    print(f'{len(args.files)} artifacts passed credential scanning')


if __name__ == '__main__':
    main()
