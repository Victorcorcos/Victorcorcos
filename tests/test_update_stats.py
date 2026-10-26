from pathlib import Path
import hashlib
import re
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError
import xml.etree.ElementTree as ET

from scripts import update_stats


def snapshot(filename):
    readme = (update_stats.ROOT / "README.md").read_text()
    paths = re.findall(
        rf'src="(\./assets/{re.escape(Path(filename).stem)}(?:-[0-9a-f]{{16}})?\.svg)"',
        readme,
    )
    if len(paths) != 1:
        raise AssertionError(f"Expected one snapshot for {filename}: {paths}")
    return update_stats.ROOT / paths[0]


class UpdateStatsTests(unittest.TestCase):
    def test_readme_urls_identify_the_exact_snapshot_contents(self):
        readme = (update_stats.ROOT / "README.md").read_text()
        for filename, *_ in update_stats.CARDS:
            path = snapshot(filename)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
            self.assertEqual(path.name, f"{Path(filename).stem}-{digest}.svg")
            self.assertIn(f'src="./assets/{path.name}"', readme)

    def test_refresh_changes_url_only_when_image_changes(self):
        data = [snapshot(filename).read_bytes() for filename, *_ in update_stats.CARDS]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            readme = root / "README.md"
            readme.write_text('\n'.join(
                f'<img src="./assets/{filename}">' for filename, *_ in update_stats.CARDS
            ))
            with patch.object(update_stats, "ROOT", root):
                with patch.object(update_stats, "fetch_card", side_effect=data):
                    update_stats.main()
                first = readme.read_text()
                with patch.object(update_stats, "fetch_card", side_effect=data):
                    update_stats.main()
                self.assertEqual(readme.read_text(), first)
                # Change valid SVG metadata without depending on text indentation.
                changed = data[1].replace(b'role="img"', b'role="img" aria-label="updated"')
                with patch.object(update_stats, "fetch_card", side_effect=[data[0], changed]):
                    update_stats.main()
                old_urls = re.findall(r'src="([^"]+)"', first)
                new_urls = re.findall(r'src="([^"]+)"', readme.read_text())
                self.assertEqual(old_urls[0], new_urls[0])
                self.assertNotEqual(old_urls[1], new_urls[1])
                self.assertTrue((root / old_urls[1]).is_file())
                for url in new_urls:
                    self.assertTrue((root / url).is_file())

    def test_card_canvases_have_equal_heights_and_fit_a_desktop_row(self):
        roots = [
            ET.parse(snapshot(filename)).getroot()
            for filename, *_ in update_stats.CARDS
        ]
        self.assertEqual(roots[0].get("height"), roots[1].get("height"))
        self.assertEqual(sum(float(root.get("width")) for root in roots), 767)
        for root in roots:
            self.assertEqual(root.get("viewBox").split()[3], root.get("height"))

    def test_committed_cards_are_valid(self):
        for filename, _, heading, content_class in update_stats.CARDS:
            with self.subTest(filename=filename):
                data = snapshot(filename).read_bytes()
                update_stats.validate_svg(data, heading, content_class)

    def test_rejects_html_svg_error_cards_and_empty_cards(self):
        heading = update_stats.CARDS[0][2]
        for data in (
            b"<html>Service unavailable</html>",
            b'<svg xmlns="http://www.w3.org/2000/svg"><text>Something went wrong!</text></svg>',
            f'<svg xmlns="http://www.w3.org/2000/svg"><text>{heading}</text></svg>'.encode(),
        ):
            with self.subTest(data=data), self.assertRaises(ValueError):
                update_stats.validate_svg(data, heading, "stat")

    @patch.object(update_stats.time, "sleep")
    @patch.object(update_stats, "urlopen")
    def test_retries_transient_failure(self, urlopen, sleep):
        filename, url, heading, content_class = update_stats.CARDS[0]
        data = snapshot(filename).read_bytes()
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers.get_content_type.return_value = "image/svg+xml"
        response.read.return_value = data
        urlopen.side_effect = [URLError("timeout"), response]
        self.assertEqual(update_stats.fetch_card(url, heading, content_class), data)
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(5)

    @patch.object(update_stats.time, "sleep")
    @patch.object(update_stats, "urlopen")
    def test_retries_http_200_error_card_then_fails(self, urlopen, sleep):
        response = urlopen.return_value.__enter__.return_value
        response.headers.get_content_type.return_value = "image/svg+xml"
        response.read.return_value = b'<svg xmlns="http://www.w3.org/2000/svg"><text>API rate limit exceeded</text></svg>'
        _, url, heading, content_class = update_stats.CARDS[0]
        with self.assertRaises(RuntimeError):
            update_stats.fetch_card(url, heading, content_class)
        self.assertEqual(urlopen.call_count, 3)

    def test_failed_second_download_preserves_both_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "assets").mkdir()
            for filename, *_ in update_stats.CARDS:
                (root / "assets" / filename).write_bytes(b"original snapshot")
            with (
                patch.object(update_stats, "ROOT", root),
                patch.object(update_stats, "fetch_card", side_effect=[b"new card", RuntimeError("timeout")]),
                self.assertRaises(RuntimeError),
            ):
                update_stats.main()
            for filename, *_ in update_stats.CARDS:
                self.assertEqual((root / "assets" / filename).read_bytes(), b"original snapshot")


if __name__ == "__main__":
    unittest.main()
