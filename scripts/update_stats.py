"""Refresh profile cards without replacing working images with error responses."""

from pathlib import Path
import hashlib
import re
import time
from urllib.error import URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://github-readme-stats2-neon.vercel.app/api"
CARDS = (
    (
        "github-stats.svg",
        f"{BASE_URL}?username=Victorcorcos&show_icons=true&include_all_commits=true",
        "Victor Cordeiro Costa's GitHub Stats",
        "stat",
    ),
    (
        "top-languages.svg",
        f"{BASE_URL}/top-langs/?username=Victorcorcos&hide_progress=true&langs_count=12",
        "Most Used Languages",
        "lang-name",
    ),
)


def validate_svg(data, heading, content_class):
    root = ET.fromstring(data)
    if root.tag != "{http://www.w3.org/2000/svg}svg":
        raise ValueError("Response is not an SVG image")
    texts = list(root.iter("{http://www.w3.org/2000/svg}text"))
    if not any("".join(node.itertext()).strip() == heading for node in texts):
        raise ValueError(f"Missing card heading: {heading}")
    if not any(content_class in node.get("class", "").split() for node in texts):
        raise ValueError("Card has no statistics")


def fetch_card(url, heading, content_class):
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "Victorcorcos-profile-stats"})
            with urlopen(request, timeout=60) as response:
                if response.headers.get_content_type() != "image/svg+xml":
                    raise ValueError("Response content type is not image/svg+xml")
                data = response.read()
            # The service can return an error card with HTTP 200 and SVG MIME type.
            validate_svg(data, heading, content_class)
            return data
        except (URLError, OSError, ValueError, ET.ParseError) as error:
            if attempt == 2:
                raise RuntimeError(f"Unable to refresh {url}") from error
            print(f"Attempt {attempt + 1} failed: {error}; retrying", flush=True)
            time.sleep(5 * (attempt + 1))


def main():
    # Download and validate both cards before touching either existing snapshot.
    cards = [
        (filename, fetch_card(url, heading, content_class))
        for filename, url, heading, content_class in CARDS
    ]
    # Match the canvas heights without scaling text or widening the language card.
    # Keeping the combined width at 767px lets GitHub wrap the images on mobile.
    height = max(float(ET.fromstring(data).get("height")) for _, data in cards)
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    readme_path = ROOT / "README.md"
    readme = readme_path.read_text()
    snapshots = []
    for filename, data in cards:
        root = ET.fromstring(data)
        root.set("height", f"{height:g}")
        root.set("viewBox", f"0 0 {root.get('width')} {height:g}")
        data = b"\n".join(
            line.rstrip() for line in ET.tostring(root, encoding="utf-8").splitlines()
        ) + b"\n"
        # A new URL for new content avoids stale browser/CDN copies of old cards.
        stem = Path(filename).stem
        digest = hashlib.sha256(data).hexdigest()[:16]
        target = assets / f"{stem}-{digest}.svg"
        pattern = rf'(?<=src=")\./assets/{re.escape(stem)}(?:-[0-9a-f]{{16}})?\.svg(?=")'
        readme, replacements = re.subn(pattern, f"./assets/{target.name}", readme)
        if replacements != 1:
            raise ValueError(f"Expected one README image for {filename}")
        snapshots.append((filename, target, data))

    for filename, target, data in snapshots:
        temporary = target.with_suffix(".svg.tmp")
        temporary.write_bytes(data)
        temporary.replace(target)
        print(f"Updated {target.relative_to(ROOT)}")
    readme_path.write_text(readme)
    # Retain old URLs so cached README pages can still load their exact images.


if __name__ == "__main__":
    main()
