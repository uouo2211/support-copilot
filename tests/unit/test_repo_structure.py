"""Static-checker tests; no third-party imports, filesystem writes or services."""

from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.check_repo import check, link_errors, local_links, requirement_errors, validate_text


class RepositoryCheckerTests(unittest.TestCase):
    def test_relative_markdown_links(self):
        text = "[next](../docs/README.md) [section](README.md#status)"
        self.assertEqual(list(local_links(text)), ["../docs/README.md", "README.md"])

    def test_external_and_anchor_links_are_not_local_files(self):
        text = "[web](https://example.org) [mail](mailto:hello@example.org) [heading](#status)"
        self.assertEqual(list(local_links(text)), [])

    def test_archived_fenced_links_are_not_rewritten_or_checked(self):
        text = "```markdown\n[old](/old/path.md)\n```\n~~~text\n[old](missing.md)\n~~~"
        self.assertEqual(list(local_links(text)), [])

    def test_angle_bracket_link_and_percent_encoding(self):
        text = "[guide](<a folder/guide.md>) [guide](a%20folder/guide.md)"
        self.assertEqual(list(local_links(text)), ["a folder/guide.md", "a folder/guide.md"])

    def test_missing_file_is_reported(self):
        with patch.object(Path, "exists", return_value=False):
            errors = link_errors(Path("/repo/README.md"), "[broken](missing.md)", Path("/repo"))
        self.assertEqual(errors, ["missing local link: missing.md"])

    def test_out_of_repository_file_is_rejected(self):
        errors = link_errors(Path("/repo/README.md"), "[private](../private.md)", Path("/repo"))
        self.assertEqual(errors, ["nonportable or out-of-repository link: ../private.md"])

    def test_exact_requirement_with_environment_marker(self):
        text = '# generated\nhttpx==0.28.1\npsycopg[binary]==3.2.9 ; python_version >= "3.12"\n'
        self.assertEqual(requirement_errors(text), [])

    def test_unpinned_requirement_is_rejected(self):
        self.assertEqual(len(requirement_errors("httpx>=0.28\npip\n-r other.txt\n")), 3)

    def test_python_is_parsed_without_execution(self):
        text = 'raise RuntimeError("must never execute")\n'
        self.assertEqual(validate_text(Path("code.py"), text, Path(".")), [])

    def test_invalid_python_is_reported(self):
        self.assertTrue(validate_text(Path("code.py"), "def broken(:", Path(".")))

    def test_invalid_json_is_reported(self):
        self.assertTrue(validate_text(Path("fixture.json"), '{"broken":}', Path(".")))

    def test_valid_json_is_accepted(self):
        self.assertEqual(validate_text(Path("fixture.json"), '[{"demo": true}]', Path(".")), [])

    def test_missing_csv_columns_are_reported(self):
        self.assertTrue(validate_text(Path("fixtures/messages.csv"), "platform\nwecom\n", Path(".")))

    def test_actual_repository_layout_and_links(self):
        _, errors = check()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
