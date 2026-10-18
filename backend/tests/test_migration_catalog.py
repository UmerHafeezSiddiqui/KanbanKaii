import importlib.util
from pathlib import Path
from unittest import TestCase


class MigrationCatalogTests(TestCase):
    def test_every_migration_test_resolves_a_real_repository_migration(self):
        tests = Path(__file__).parent
        migrations = tests.parents[1] / 'supabase' / 'migrations'
        for source in tests.glob('test_*migration.py'):
            with self.subTest(test=source.name):
                spec = importlib.util.spec_from_file_location(source.stem, source)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self.assertEqual(module.MIGRATION.parent, migrations)
                self.assertTrue(module.MIGRATION.is_file(), str(module.MIGRATION))
