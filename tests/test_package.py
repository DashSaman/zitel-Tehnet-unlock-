import unittest

from tools.audit_public import ROOT, public_files


class PackageOrderTests(unittest.TestCase):
    def test_archive_paths_have_platform_independent_order(self):
        paths = [path.relative_to(ROOT).as_posix() for path in public_files()]
        self.assertEqual(paths, sorted(paths))
