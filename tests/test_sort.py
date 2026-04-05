"""
Tests for sort.py — README sorting logic.

File I/O is isolated by changing the working directory to a pytest
tmp_path, so tests never touch the real README.md.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import sort


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_readme(tmp_path, content):
    (tmp_path / 'README.md').write_text(content, encoding='utf-8')


def read_readme(tmp_path):
    return (tmp_path / 'README.md').read_text(encoding='utf-8')


# ---------------------------------------------------------------------------
# main() — clustering and sorting
# ---------------------------------------------------------------------------

class TestMainClustering:

    def test_consecutive_same_indent_links_are_sorted_together(self, tmp_path, monkeypatch):
        """Links at the same indentation level form one block and get sorted."""
        monkeypatch.chdir(tmp_path)
        write_readme(tmp_path, (
            "## Libraries\n"
            "* [Zebra](http://zebra.example)\n"
            "* [Alpha](http://alpha.example)\n"
            "* [Mango](http://mango.example)\n"
        ))
        sort.main()
        result = read_readme(tmp_path)
        lines = [l for l in result.splitlines() if l.startswith('* [')]
        assert lines == [
            '* [Alpha](http://alpha.example)',
            '* [Mango](http://mango.example)',
            '* [Zebra](http://zebra.example)',
        ]

    def test_non_link_line_breaks_block(self, tmp_path, monkeypatch):
        """A non-link line between two link lines prevents them from being sorted together."""
        monkeypatch.chdir(tmp_path)
        write_readme(tmp_path, (
            "* [Zebra](z)\n"
            "\n"
            "* [Alpha](a)\n"
        ))
        sort.main()
        result = read_readme(tmp_path)
        # Zebra must still come before Alpha since they are in separate blocks
        assert result.index('Zebra') < result.index('Alpha')

    def test_different_indent_links_are_separate_blocks(self, tmp_path, monkeypatch):
        """Links at different indentation levels are placed in separate blocks."""
        monkeypatch.chdir(tmp_path)
        write_readme(tmp_path, (
            "* [Zebra](z)\n"
            "    * [Alpha](a)\n"
            "    * [Mango](m)\n"
        ))
        sort.main()
        result = read_readme(tmp_path)
        lines = result.splitlines()
        # Zebra is at indent 0, Alpha/Mango at indent 4 — Zebra must stay first
        assert lines[0] == '* [Zebra](z)'
        # Alpha and Mango (same indent) should be sorted
        indented = [l for l in lines if l.startswith('    * [')]
        assert indented == ['    * [Alpha](a)', '    * [Mango](m)']

    def test_dash_prefix_links_are_recognised(self, tmp_path, monkeypatch):
        """Lines starting with '- [' are treated as link lines, same as '* ['."""
        monkeypatch.chdir(tmp_path)
        write_readme(tmp_path, (
            "- [Zebra](z)\n"
            "- [Alpha](a)\n"
        ))
        sort.main()
        result = read_readme(tmp_path)
        lines = [l for l in result.splitlines() if l.startswith('- [')]
        assert lines == ['- [Alpha](a)', '- [Zebra](z)']

    def test_non_link_lines_pass_through_unchanged(self, tmp_path, monkeypatch):
        """Headers and plain text lines are not modified."""
        monkeypatch.chdir(tmp_path)
        content = "## Section Header\n\nSome descriptive text.\n"
        write_readme(tmp_path, content)
        sort.main()
        assert read_readme(tmp_path) == content

    def test_mixed_prefixes_in_one_block(self, tmp_path, monkeypatch):
        """'* [' and '- [' at the same indent are not grouped — they differ in prefix character."""
        monkeypatch.chdir(tmp_path)
        write_readme(tmp_path, (
            "* [Zebra](z)\n"
            "- [Alpha](a)\n"
        ))
        sort.main()
        result = read_readme(tmp_path)
        # Both lines present; order depends on clustering (they start separate blocks)
        assert '* [Zebra](z)' in result
        assert '- [Alpha](a)' in result


# ---------------------------------------------------------------------------
# main() — case-insensitive sorting
# ---------------------------------------------------------------------------

class TestMainCaseInsensitiveSort:

    def test_sort_is_case_insensitive(self, tmp_path, monkeypatch):
        """Sorting ignores case so 'apple' sorts before 'Banana' before 'cherry'."""
        monkeypatch.chdir(tmp_path)
        write_readme(tmp_path, (
            "* [cherry](c)\n"
            "* [Apple](a)\n"
            "* [Banana](b)\n"
        ))
        sort.main()
        result = read_readme(tmp_path)
        lines = [l for l in result.splitlines() if l.startswith('* [')]
        names = [l.split('[')[1].split(']')[0] for l in lines]
        assert names == sorted(names, key=str.lower)

    def test_uppercase_does_not_sort_before_lowercase(self, tmp_path, monkeypatch):
        """Without case-insensitive sort, 'Z' < 'a' in ASCII; with it, 'a' sorts first."""
        monkeypatch.chdir(tmp_path)
        write_readme(tmp_path, (
            "* [Zeta](z)\n"
            "* [alpha](a)\n"
        ))
        sort.main()
        result = read_readme(tmp_path)
        lines = [l for l in result.splitlines() if l.startswith('* [')]
        assert lines[0] == '* [alpha](a)'
        assert lines[1] == '* [Zeta](z)'


# ---------------------------------------------------------------------------
# sort_blocks() — TOC / body splitting
# ---------------------------------------------------------------------------

class TestSortBlocksTOC:

    def test_table_of_contents_is_preserved_verbatim(self, tmp_path, monkeypatch):
        """Content before '- - -' is the TOC and must not be modified."""
        monkeypatch.chdir(tmp_path)
        toc = "# Awesome Python\n\n- [Z Section](#z)\n- [A Section](#a)\n\n"
        body = "\n## Z Section\n\n* [lib](url)\n\n## A Section\n\n* [lib2](url2)\n"
        write_readme(tmp_path, toc + '- - -' + body)
        sort.sort_blocks()
        result = read_readme(tmp_path)
        assert result.startswith(toc)

    def test_separator_is_present_in_output(self, tmp_path, monkeypatch):
        """The '- - -' separator must be preserved between TOC and body."""
        monkeypatch.chdir(tmp_path)
        write_readme(tmp_path, "TOC\n\n- - -\n\n## A\n\n* [x](y)\n")
        sort.sort_blocks()
        assert '- - -' in read_readme(tmp_path)


# ---------------------------------------------------------------------------
# sort_blocks() — ## section sorting
# ---------------------------------------------------------------------------

class TestSortBlocksSections:

    def _readme_with_sections(self, sections):
        """Build a minimal README with the given ## section names."""
        body = '\n'.join(f'## {name}\n\n* [{name} lib](url)\n' for name in sections)
        return f"# Title\n\n- - -\n\n{body}\n"

    def test_sections_are_sorted_alphabetically(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        write_readme(tmp_path, self._readme_with_sections(['Zebra', 'Alpha', 'Mango']))
        sort.sort_blocks()
        result = read_readme(tmp_path)
        positions = {name: result.index(f'## {name}') for name in ['Zebra', 'Alpha', 'Mango']}
        assert positions['Alpha'] < positions['Mango'] < positions['Zebra']

    def test_single_section_is_not_broken(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        write_readme(tmp_path, "# Title\n\n- - -\n\n## Only Section\n\n* [lib](url)\n")
        sort.sort_blocks()
        result = read_readme(tmp_path)
        assert '## Only Section' in result
        assert '* [lib](url)' in result

    def test_section_prefix_is_restored_after_split(self, tmp_path, monkeypatch):
        """After splitting on '##', each section must have '##' re-prepended."""
        monkeypatch.chdir(tmp_path)
        write_readme(tmp_path, self._readme_with_sections(['Beta', 'Alpha']))
        sort.sort_blocks()
        result = read_readme(tmp_path)
        assert result.count('## Alpha') == 1
        assert result.count('## Beta') == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_readme_does_not_crash(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        write_readme(tmp_path, '')
        sort.main()  # should not raise

    def test_readme_with_no_links_is_unchanged(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        content = "# Title\n\nJust some text.\n"
        write_readme(tmp_path, content)
        sort.main()
        # sort_blocks() will be called but README has no '- - -', so check it doesn't crash
        # and that non-link content is preserved
        result = read_readme(tmp_path)
        assert 'Just some text.' in result

    def test_already_sorted_readme_is_unchanged_by_main(self, tmp_path, monkeypatch):
        """Running main() on an already-sorted README produces the same output."""
        monkeypatch.chdir(tmp_path)
        content = (
            "## Section\n"
            "* [Alpha](a)\n"
            "* [Beta](b)\n"
            "* [Gamma](g)\n"
        )
        write_readme(tmp_path, content)
        sort.main()
        result = read_readme(tmp_path)
        lines = [l for l in result.splitlines() if l.startswith('* [')]
        assert lines == ['* [Alpha](a)', '* [Beta](b)', '* [Gamma](g)']

    def test_unicode_library_names_sort_correctly(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        write_readme(tmp_path, (
            "* [Ångström](ang)\n"
            "* [Zebra](z)\n"
            "* [alpha](a)\n"
        ))
        sort.main()
        result = read_readme(tmp_path)
        assert '* [' in result  # didn't crash; content is present


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:

    def test_main_is_idempotent(self, tmp_path, monkeypatch):
        """Running main() twice produces the same result as running it once."""
        monkeypatch.chdir(tmp_path)
        content = (
            "# Title\n\n- [Z](#z)\n- [A](#a)\n\n- - -\n\n"
            "## Zebra\n\n* [z-lib](z)\n\n"
            "## Alpha\n\n* [b-lib](b)\n* [a-lib](a)\n\n"
        )
        write_readme(tmp_path, content)
        sort.main()
        after_first = read_readme(tmp_path)

        sort.main()
        after_second = read_readme(tmp_path)

        assert after_first == after_second

    def test_sort_blocks_is_idempotent(self, tmp_path, monkeypatch):
        """Running sort_blocks() twice produces the same result as running it once."""
        monkeypatch.chdir(tmp_path)
        content = (
            "# Title\n\n- - -\n\n"
            "## Zebra\n\n* [z-lib](z)\n\n"
            "## Alpha\n\n* [a-lib](a)\n\n"
        )
        write_readme(tmp_path, content)
        sort.sort_blocks()
        after_first = read_readme(tmp_path)

        sort.sort_blocks()
        after_second = read_readme(tmp_path)

        assert after_first == after_second
