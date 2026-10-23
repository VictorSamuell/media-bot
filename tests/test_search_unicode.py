import tempfile
import unittest
from pathlib import Path

from media_bot.library import Library


class SearchUnicodeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = Library(self.root / 'library')
        self.source = self.root / 'sample.pdf'
        self.source.write_bytes(b'test')

    def save_named(self, name, owner=42):
        file_id = self.library.save_local(self.source, owner)
        self.library.rename(owner, file_id, name)
        return file_id

    def test_accents_case_and_original_name_after_reopening(self):
        file_id = self.save_named('Relatório de AÇÃO.pdf')
        self.save_named('Relatório de AÇÃO.pdf', owner=99)
        reopened = Library(self.library.root)
        for term in ('relatorio', 'RELATÓRIO', 'acao', 'AÇÃO', '  acao  '):
            with self.subTest(term=term):
                rows = reopened.search(42, term)
                self.assertEqual([row['id'] for row in rows], [file_id])
                self.assertEqual(rows[0]['name'], 'Relatório de AÇÃO.pdf')
        self.assertEqual(reopened.search(100, 'acao'), [])

    def test_composed_and_decomposed_accents_match(self):
        file_id = self.save_named('cafe\u0301.pdf')
        for term in ('café', 'CAFE', 'cafe\u0301'):
            self.assertEqual(self.library.search(42, term)[0]['id'], file_id)

    def test_empty_terms_and_sql_wildcards_are_not_match_all(self):
        self.save_named('Relatório.pdf')
        for term in ('', '   ', '\u0301', '%', '_', "' OR 1=1 --"):
            with self.subTest(term=term):
                self.assertEqual(self.library.search(42, term), [])
        file_id = self.save_named('100%_concluído.pdf')
        self.assertEqual(self.library.search(42, '%_')[0]['id'], file_id)

    def test_limit_and_newest_first_are_preserved(self):
        identifiers = [self.save_named(f'AÇÃO {number}.pdf') for number in range(12)]
        results = self.library.search(42, 'acao')
        self.assertEqual([row['id'] for row in results], list(reversed(identifiers))[:10])
