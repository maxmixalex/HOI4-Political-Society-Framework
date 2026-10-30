"""Every party and ideology has two sizes, with independent authored overrides."""
from pathlib import Path
import tempfile
import unittest

from psf import icons


class IdentityIconTests(unittest.TestCase):
    def fixture(self):
        return {"axes": [{"id": "economy", "weight": 2}], "ideologies": [
            {"id": "liberal", "engine_ideology": "democratic", "positions": {"economy": 50}},
            {"id": "socialist", "engine_ideology": "communism", "positions": {"economy": -50}}],
            "profiles": [{"groups": [
                {"id": "party_a", "kind": "party", "positions": {"economy": 30}},
                {"id": "party_b", "kind": "party", "positions": {"economy": -30}},
                {"id": "workers", "kind": "trade_union", "positions": {"economy": -40}}]}],
            "fallback_profiles": [{"groups": [{"id": "generic_party", "kind": "party"}]}]}

    def test_every_registered_identity_has_a_gui_icon_and_texticon(self):
        manifest = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = icons.generate_icons(manifest, root)
            gfx = (root / "interface/psf_identity_icons.gfx").read_text()
            self.assertEqual(len(report["groups"]), 4)
            self.assertEqual(len(report["ideologies"]), 2)
            for collection in (report["groups"], report["ideologies"]):
                for item in collection.values():
                    for size in ("large", "small"):
                        self.assertIn('name = "' + item[size] + '"', gfx)
                    self.assertEqual(item["texticon"], "£" + item["small"].removeprefix("GFX_") + "£")
            self.assertEqual(gfx.count("legacy_lazy_load = no"), 12)
            self.assertFalse(list(root.rglob("*.tga")))

    def test_native_defaults_follow_category_or_nearest_archetype(self):
        manifest = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = icons.generate_icons(manifest, root)
            self.assertIn("gfx/interface/ideologies/democratic_group.dds", report["native_textures"])
            self.assertIn("gfx/interface/ideologies/communism_group.dds", report["native_textures"])
            self.assertIn("gfx/interface/ideas/generic_manpower_bonus.dds", report["native_textures"])
            self.assertEqual(icons.closest_ideology(manifest, manifest["profiles"][0]["groups"][1])["id"], "socialist")

    def test_custom_sources_override_sizes_independently_without_duplicate_definitions(self):
        manifest = self.fixture()
        group = manifest["profiles"][0]["groups"][0]
        group.update(large_icon="GFX_author_party_portrait", small_icon="GFX_author_party_texticon")
        archetype = manifest["ideologies"][0]
        archetype["small_icon"] = "GFX_author_archetype_texticon"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = icons.generate_icons(manifest, root)
            gfx = (root / "interface/psf_identity_icons.gfx").read_text()
            self.assertEqual(icons.sprite(group), "GFX_author_party_portrait")
            self.assertEqual(icons.texticon(group), "£author_party_texticon£")
            self.assertEqual(icons.texticon(archetype, "ideology"), "£author_archetype_texticon£")
            self.assertEqual(len(report["custom_sprites"]), 3)
            self.assertNotIn('name = "GFX_author_', gfx)
            self.assertIn('name = "GFX_psf_ideology_liberal_large"', gfx)

    def test_native_aliases_are_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a = icons.generate_icons(self.fixture(), root / "a")
            b = icons.generate_icons(self.fixture(), root / "b")
            self.assertEqual(a, b)
            self.assertEqual((root / "a/interface/psf_identity_icons.gfx").read_bytes(),
                             (root / "b/interface/psf_identity_icons.gfx").read_bytes())
