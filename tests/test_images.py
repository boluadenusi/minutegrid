import json
import tempfile
import unittest
from pathlib import Path

from scripts.images import club_with_logo, load_images, player_image


class ImagesTest(unittest.TestCase):
    def test_logo_by_club_id_then_league_and_name(self):
        images = {"players": {"7": "p.webp"}, "clubs": {"11": "arsenal.webp"}, "teams": {"GB1|Coventry City": "cov.webp"}}
        self.assertEqual(club_with_logo(images, {"name": "Arsenal FC", "id": "11"})["logo"], "arsenal.webp")
        self.assertEqual(club_with_logo(images, {"name": "Coventry City", "id": None}, "GB1")["logo"], "cov.webp")
        self.assertNotIn("logo", club_with_logo(images, {"name": "Leeds", "id": "399"}, "GB1"))
        self.assertIsNone(club_with_logo(images, None))
        self.assertEqual(player_image(images, 7), "p.webp")

    def test_missing_file_means_no_images(self):
        self.assertEqual(load_images(Path(tempfile.mkdtemp()) / "images.json"),
                         {"players": {}, "clubs": {}, "teams": {}, "leagues": {}})
        path = Path(tempfile.mkdtemp()) / "images.json"
        path.write_text(json.dumps({"players": {"1": "x"}}), encoding="utf-8")
        self.assertEqual(load_images(path)["players"], {"1": "x"})


if __name__ == "__main__":
    unittest.main()
