"""Lint tests using Python's built-in ast/compile — no external linter needed.

Checks every .py file under app/ for:
  1. Syntax validity (ast.parse / compile)
  2. No bare `except:` clauses (should always specify exception type)
  3. No wildcard imports (`from x import *`)
  4. No print() calls in production code (use logging instead)
  5. No TODO/FIXME/HACK/XXX left in comments
  6. Files end with a newline
  7. No tabs used for indentation (spaces only)
"""
import ast
import os
import tokenize
import io
import pytest
from pathlib import Path

# Root of the application source code
APP_ROOT = Path(__file__).resolve().parent.parent / "app"


def _collect_py_files() -> list[Path]:
    """Gather all .py files under app/."""
    return sorted(APP_ROOT.rglob("*.py"))


PY_FILES = _collect_py_files()


def _ids(paths: list[Path]) -> list[str]:
    """Short ids for parametrise — show path relative to backend/."""
    backend = APP_ROOT.parent
    return [str(p.relative_to(backend)) for p in paths]


# ── 1. Syntax validity ──────────────────────────────────────────────────

class TestSyntax:
    @pytest.mark.parametrize("filepath", PY_FILES, ids=_ids(PY_FILES))
    def test_file_compiles(self, filepath: Path):
        """Every source file must be valid Python."""
        source = filepath.read_text(encoding="utf-8")
        compile(source, str(filepath), "exec")

    @pytest.mark.parametrize("filepath", PY_FILES, ids=_ids(PY_FILES))
    def test_file_parses_to_ast(self, filepath: Path):
        """Every source file must produce a valid AST."""
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
        assert isinstance(tree, ast.Module)


# ── 2. No bare except ───────────────────────────────────────────────────

class TestNoBareExcept:
    @pytest.mark.parametrize("filepath", PY_FILES, ids=_ids(PY_FILES))
    def test_no_bare_except(self, filepath: Path):
        """Bare `except:` is dangerous — always specify an exception type."""
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
        bare: list[int] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                bare.append(node.lineno)
        assert bare == [], (
            f"Bare except at line(s) {bare} in {filepath.name}. "
            "Use `except Exception:` instead."
        )


# ── 3. No wildcard imports ──────────────────────────────────────────────

class TestNoWildcardImport:
    @pytest.mark.parametrize("filepath", PY_FILES, ids=_ids(PY_FILES))
    def test_no_star_import(self, filepath: Path):
        """`from x import *` pollutes the namespace."""
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
        stars: list[int] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        stars.append(node.lineno)
        assert stars == [], (
            f"Wildcard import at line(s) {stars} in {filepath.name}"
        )


# ── 4. No print() in production code ────────────────────────────────────

class TestNoPrint:
    @pytest.mark.parametrize("filepath", PY_FILES, ids=_ids(PY_FILES))
    def test_no_print_calls(self, filepath: Path):
        """Production code should use logging, not print()."""
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
        prints: list[int] = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
            ):
                prints.append(node.lineno)
        assert prints == [], (
            f"print() at line(s) {prints} in {filepath.name}. "
            "Use logger instead."
        )


# ── 5. No stale TODO/FIXME markers ──────────────────────────────────────

MARKER_TAGS = ("TODO", "FIXME", "HACK", "XXX")


class TestNoStaleMarkers:
    @pytest.mark.parametrize("filepath", PY_FILES, ids=_ids(PY_FILES))
    def test_no_todo_fixme_markers(self, filepath: Path):
        """Flag leftover TODO/FIXME/HACK/XXX in comments."""
        source = filepath.read_text(encoding="utf-8")
        hits: list[tuple[int, str]] = []
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for tok_type, tok_string, (srow, _), _, _ in tokens:
            if tok_type == tokenize.COMMENT:
                upper = tok_string.upper()
                for tag in MARKER_TAGS:
                    if tag in upper:
                        hits.append((srow, tag))
        assert hits == [], (
            f"Stale markers in {filepath.name}: "
            + ", ".join(f"line {ln}: {tag}" for ln, tag in hits)
        )


# ── 6. Files end with newline ────────────────────────────────────────────

class TestTrailingNewline:
    @pytest.mark.parametrize("filepath", PY_FILES, ids=_ids(PY_FILES))
    def test_ends_with_newline(self, filepath: Path):
        """POSIX convention: text files should end with a newline."""
        raw = filepath.read_bytes()
        if len(raw) == 0:
            return  # empty __init__.py is fine
        assert raw.endswith(b"\n"), f"{filepath.name} does not end with a newline"


# ── 7. No tab indentation ───────────────────────────────────────────────

class TestNoTabs:
    @pytest.mark.parametrize("filepath", PY_FILES, ids=_ids(PY_FILES))
    def test_no_tab_indentation(self, filepath: Path):
        """Use spaces, not tabs."""
        lines = filepath.read_text(encoding="utf-8").splitlines()
        tab_lines = [i + 1 for i, line in enumerate(lines) if line.startswith("\t")]
        assert tab_lines == [], (
            f"Tab indentation at line(s) {tab_lines} in {filepath.name}"
        )
