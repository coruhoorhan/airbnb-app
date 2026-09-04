import ast
import logging
from magda_agent.security.mcp_kernel_taint import is_tainted
from magda_agent.security.mcp_kernel_fs import MCPKernelFS

import builtins
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Exception raised for security violations in MCPKernel."""
    pass


class MCPKernel:
    """
    MCPKernel provides a narrow, Python-only execution environment for simple
    data transformations. It rejects imports, attributes, dynamic call targets,
    generator/comprehension frame tricks, and reassignment of allowed builtins.
    """

    def __init__(self, allowed_builtins: Optional[Set[str]] = None, allowed_fs: Optional[MCPKernelFS] = None, max_ast_nodes: int = 1000):
        self.allowed_fs = allowed_fs
        self.max_ast_nodes = max_ast_nodes
        self.execution_log: List[Dict[str, Any]] = []
        self.allowed_builtins = allowed_builtins or {
            "print", "len", "range", "int", "str", "float", "list", "dict",
            "set", "tuple", "bool",
        }
        self.unsafe_calls = {"open", "exec", "eval", "__import__"}
        self._unsafe_names = self.unsafe_calls | {
            "__builtins__", "breakpoint", "classmethod", "compile", "delattr",
            "dir", "getattr", "globals", "hasattr", "help", "input", "locals",
            "memoryview", "object", "property", "setattr", "staticmethod", "super",
            "type", "vars",
        }

    def is_safe(self, code: str) -> bool:
        try:
            tree = ast.parse(code)
            _MCPValidator(self.allowed_builtins, self._unsafe_names, self.max_ast_nodes).visit(tree)
            return True
        except (SyntaxError, SecurityError) as e:
            logger.warning(f"Validation failed: {e}")
            return False

    def execute(self, code: str, globals_dict: Optional[Dict[str, Any]] = None, locals_dict: Optional[Dict[str, Any]] = None) -> Any:
        log_entry = {"code": code, "status": "unknown"}
        self.execution_log.append(log_entry)
        if len(self.execution_log) > 100:
            self.execution_log.pop(0)

        try:
            if is_tainted(code):
                raise SecurityError("Code is tainted and unsafe to execute.")
            if globals_dict is not None and is_tainted(globals_dict):
                raise SecurityError("globals_dict is tainted and unsafe to use in execution.")
            if locals_dict is not None and is_tainted(locals_dict):
                raise SecurityError("locals_dict is tainted and unsafe to use in execution.")
            if not self.is_safe(code):
                raise SecurityError("Code contains unsafe operations and was blocked by MCPKernel taint tracking.")

            safe_builtins = {name: getattr(builtins, name) for name in self.allowed_builtins if hasattr(builtins, name)}

            # Support file operations if sandboxed FS is provided
            if self.allowed_fs:
                safe_builtins["open"] = self.allowed_fs.open
                if "open" in self._unsafe_names:
                    self._unsafe_names.remove("open")
                self.allowed_builtins.add("open")
            else:
                if "open" not in self._unsafe_names:
                    self._unsafe_names.add("open")
                if "open" in self.allowed_builtins:
                    self.allowed_builtins.remove("open")

            execution_globals: Dict[str, Any] = {}
            if globals_dict:
                execution_globals.update({k: v for k, v in globals_dict.items() if k != "__builtins__"})
            execution_globals["__builtins__"] = safe_builtins

            if locals_dict is None:
                locals_dict = {}

            exec(compile(ast.parse(code), "<mcp-kernel>", "exec"), execution_globals, locals_dict)
            log_entry["status"] = "success"
            logger.info("Execution successful")
            return locals_dict
        except SecurityError as e:
            log_entry["status"] = "blocked"
            log_entry["error"] = str(e)
            logger.warning(f"Execution blocked: {e}")
            raise
        except Exception as e:
            log_entry["status"] = "error"
            log_entry["error"] = str(e)
            logger.error(f"Execution failed: {e}")
            raise RuntimeError(f"Execution failed: {e}")

class _MCPValidator(ast.NodeVisitor):
    _allowed_nodes = (
        ast.Module, ast.Expr, ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Name,
        ast.Load, ast.Store, ast.Constant, ast.BinOp, ast.UnaryOp, ast.BoolOp,
        ast.Compare, ast.If, ast.For, ast.While, ast.Break, ast.Continue, ast.Pass,
        ast.Call, ast.keyword, ast.List, ast.Tuple, ast.Set, ast.Dict, ast.Subscript,
        ast.Slice, ast.JoinedStr, ast.FormattedValue,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
        ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or, ast.Eq, ast.NotEq, ast.Lt,
        ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Is, ast.IsNot,
    )

    def __init__(self, allowed_builtins: Set[str], unsafe_names: Set[str], max_ast_nodes: int):
        self.allowed_builtins = allowed_builtins
        self.unsafe_names = unsafe_names
        self.max_ast_nodes = max_ast_nodes
        self.node_count = 0

    def generic_visit(self, node: ast.AST) -> None:
        self.node_count += 1
        if self.node_count > self.max_ast_nodes:
            raise SecurityError(f"Exceeded maximum AST node limit ({self.max_ast_nodes})")
        if not isinstance(node, self._allowed_nodes):
            raise SecurityError(f"Blocked unsafe syntax: {type(node).__name__}")
        super().generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        raise SecurityError("Imports are disabled")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        raise SecurityError("Imports are disabled")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        raise SecurityError("Attribute access is disabled")

    def visit_Lambda(self, node: ast.Lambda) -> None:
        raise SecurityError("Dynamic function creation is disabled")

    def visit_ListComp(self, node: ast.ListComp) -> None:
        raise SecurityError("Comprehensions are disabled")

    def visit_SetComp(self, node: ast.SetComp) -> None:
        raise SecurityError("Comprehensions are disabled")

    def visit_DictComp(self, node: ast.DictComp) -> None:
        raise SecurityError("Comprehensions are disabled")

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        raise SecurityError("Generator expressions are disabled")

    def visit_Name(self, node: ast.Name) -> None:
        if node.id.startswith("_") or node.id in self.unsafe_names:
            raise SecurityError(f"Blocked unsafe name: {node.id}")

    def visit_Call(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Name):
            raise SecurityError("Dynamic call targets are disabled")
        if node.func.id in self.unsafe_names or node.func.id not in self.allowed_builtins:
            raise SecurityError(f"Blocked unsafe call: {node.func.id}")
        for arg in node.args:
            self.visit(arg)
        for keyword in node.keywords:
            self.visit(keyword)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._check_assignment_target(target)
        self.visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._check_assignment_target(node.target)
        if node.value is not None:
            self.visit(node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._check_assignment_target(node.target)
        self.visit(node.value)

    def _check_assignment_target(self, target: ast.AST) -> None:
        for child in ast.walk(target):
            if isinstance(child, ast.Name):
                if child.id in self.allowed_builtins or child.id.startswith("_") or child.id in self.unsafe_names:
                    raise SecurityError(f"Blocked unsafe assignment target: {child.id}")
            elif isinstance(child, ast.Attribute):
                raise SecurityError("Attribute assignment is disabled")
