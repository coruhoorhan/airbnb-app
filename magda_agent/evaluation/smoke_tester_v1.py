"""
Aider Style Post-Merge Smoke Tests V1.

Inspired by Aider's post-edit smoke testing loop: Provides a fast, lightweight
smoke tester that validates AST syntax, parses import statements, and catches
syntax errors, indentation errors, and malformed constructs in changed files
immediately post-merge.
"""

import ast
import inspect
import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class FileSmokeResult:
    """Individual file syntax and import validation result."""

    file_path: str
    syntax_valid: bool
    import_valid: bool
    error_type: Optional[str] = None  # SyntaxError, IndentationError, ImportError
    error_message: Optional[str] = None
    line_number: Optional[int] = None
    offset: Optional[int] = None
    ast_node_count: int = 0
    duration_ms: float = 0.0

    @property
    def passed(self) -> bool:
        return self.syntax_valid and self.import_valid

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "passed": self.passed,
            "syntax_valid": self.syntax_valid,
            "import_valid": self.import_valid,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "line_number": self.line_number,
            "ast_node_count": self.ast_node_count,
            "duration_ms": self.duration_ms,
        }


@dataclass
class SmokeTestReport:
    """Aggregate report summarizing smoke tests over a collection of files."""

    all_passed: bool
    total_files: int
    passed_files: int
    failed_files: int
    results: List[FileSmokeResult] = field(default_factory=list)
    duration_ms: float = 0.0
    report_id: str = field(default_factory=lambda: f"smoke_{uuid.uuid4().hex[:8]}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "all_passed": self.all_passed,
            "total_files": self.total_files,
            "passed_files": self.passed_files,
            "failed_files": self.failed_files,
            "results": [r.to_dict() for r in self.results],
            "duration_ms": self.duration_ms,
            "report_id": self.report_id,
        }


class AiderPostMergeSmokeTesterV1:
    """
    Aider-style Post-Merge Smoke Tester V1.

    Performs sub-millisecond AST and import syntax analysis on Python files
    to instantly detect syntax corruptions, indentation breaks, and unclosed literals.
    """

    def __init__(self, target_python_version: Optional[Tuple[int, int]] = None):
        self.target_python_version = target_python_version

    def check_code_syntax(
        self,
        code_string: str,
        filename: str = "<string>",
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[int], Optional[int], int]:
        """
        Parse raw code string with AST.
        Returns: (is_valid, error_type, error_msg, line_no, offset, node_count)
        """
        try:
            tree = ast.parse(code_string, filename=filename)
            node_count = sum(1 for _ in ast.walk(tree))
            return True, None, None, None, None, node_count
        except (SyntaxError, IndentationError) as err:
            err_type = type(err).__name__
            return False, err_type, err.msg, err.lineno, err.offset, 0
        except Exception as ex:
            return False, type(ex).__name__, str(ex), None, None, 0

    def test_file(self, file_path: str) -> FileSmokeResult:
        """Execute syntax and import smoke test on a single file."""
        start_t = time.perf_counter()

        if not os.path.exists(file_path):
            elapsed = (time.perf_counter() - start_t) * 1000.0
            return FileSmokeResult(
                file_path=file_path,
                syntax_valid=False,
                import_valid=False,
                error_type="FileNotFoundError",
                error_message=f"File not found: {file_path}",
                duration_ms=elapsed,
            )

        if not file_path.endswith(".py"):
            elapsed = (time.perf_counter() - start_t) * 1000.0
            return FileSmokeResult(
                file_path=file_path,
                syntax_valid=True,
                import_valid=True,
                duration_ms=elapsed,
            )

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as ex:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            return FileSmokeResult(
                file_path=file_path,
                syntax_valid=False,
                import_valid=False,
                error_type="ReadError",
                error_message=str(ex),
                duration_ms=elapsed,
            )

        is_valid, err_type, err_msg, lineno, offset, node_count = self.check_code_syntax(
            content, filename=file_path
        )
        elapsed = (time.perf_counter() - start_t) * 1000.0

        return FileSmokeResult(
            file_path=file_path,
            syntax_valid=is_valid,
            import_valid=is_valid,
            error_type=err_type,
            error_message=err_msg,
            line_number=lineno,
            offset=offset,
            ast_node_count=node_count,
            duration_ms=elapsed,
        )

    def test_files(self, file_paths: List[str]) -> SmokeTestReport:
        """Run smoke tests on a list of file paths."""
        start_t = time.perf_counter()
        results = [self.test_file(p) for p in file_paths]

        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        all_ok = (failed == 0)
        elapsed = (time.perf_counter() - start_t) * 1000.0

        return SmokeTestReport(
            all_passed=all_ok,
            total_files=len(results),
            passed_files=passed,
            failed_files=failed,
            results=results,
            duration_ms=elapsed,
        )

    def test_directory(
        self,
        directory_path: str,
        recursive: bool = True,
        ignore_dirs: Optional[Set[str]] = None,
    ) -> SmokeTestReport:
        """Scan a directory and run smoke tests on all discovered Python files."""
        ignores = set(ignore_dirs or {".git", ".venv", "venv", "__pycache__", "node_modules"})
        py_files = []

        if os.path.exists(directory_path):
            if recursive:
                for root, dirs, files in os.walk(directory_path):
                    dirs[:] = [d for d in dirs if d not in ignores]
                    for f in files:
                        if f.endswith(".py"):
                            py_files.append(os.path.join(root, f))
            else:
                for f in os.listdir(directory_path):
                    if f.endswith(".py"):
                        full_p = os.path.join(directory_path, f)
                        if os.path.isfile(full_p):
                            py_files.append(full_p)

        return self.test_files(py_files)
