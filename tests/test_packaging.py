"""Every bundled native snapshot must survive installation of the compiler."""
from pathlib import Path
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PackagedNativeAssetTests(unittest.TestCase):
    def test_all_native_snapshots_are_declared_as_package_data(self):
        config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        patterns = config["tool"]["setuptools"]["package-data"]["psf"]
        package = ROOT / "psf"
        included = {path.relative_to(package) for pattern in patterns for path in package.glob(pattern) if path.is_file()}
        required = {path.relative_to(package) for directory in (package / "assets").glob("native_*")
                    for path in directory.rglob("*") if path.is_file() and path.suffix in (".txt", ".gui", ".gfx")}
        self.assertGreater(len(required), 370)
        self.assertIn(Path("assets/native_politics/common/occupation_laws/occupation_laws.txt"), required)
        self.assertFalse(required - included, "Native source snapshots omitted from installed package: " +
                         ", ".join(path.as_posix() for path in sorted(required - included)))


if __name__ == "__main__":
    unittest.main()
