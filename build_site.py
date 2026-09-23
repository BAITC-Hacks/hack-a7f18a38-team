"""Prepare the allowlisted static site files for hosting; never copy bot secrets."""
from pathlib import Path
import shutil

ROOT = Path(__file__).parent
FILES = ("index.html", "styles.css", "app.js", "catalog-data.js", "data/original-preview.html")


def main():
    for name in FILES:
        destination = ROOT / "dist" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    print("Static site files prepared in dist/.")


if __name__ == "__main__":
    main()
