import os
from pathlib import Path
from typing import Any, IO, List, Optional, Union




class MCPKernelFS:
    """
    MCPKernelFS provides a sandboxed interface for file system operations.
    It restricts file access to explicitly allowed directories during tool execution.
    """

    def __init__(self, allowed_directories: List[Union[str, Path]]):
        """
        Initialize the MCPKernelFS with a list of allowed directories.

        Args:
            allowed_directories: A list of paths representing allowed directories.
        """
        self.allowed_directories: List[Path] = [Path(d).resolve() for d in allowed_directories]


    def _raise_security_error(self, message: str) -> None:
        from magda_agent.security.mcp_kernel import SecurityError
        raise SecurityError(message)

    def _get_resolved_allowed_path(self, target_path: Path) -> Path:
        """
        Check if the resolved target path falls within any of the allowed directories.

        Args:
            target_path: The path to check.

        Returns:
            Path: The resolved path if allowed.

        Raises:
            SecurityError: If the path is outside allowed directories.
        """
        resolved_path = target_path.resolve()
        for allowed_dir in self.allowed_directories:
            try:
                # Check if resolved_path is relative to allowed_dir (i.e., inside it)
                resolved_path.relative_to(allowed_dir)
                return resolved_path
            except ValueError:
                continue
        self._raise_security_error(f"Access to path '{target_path}' is denied by MCPKernelFS.")

    def open(self, file_path: Union[str, Path], mode: str = "r", **kwargs: Any) -> IO[Any]:
        """
        Open a file if it falls within the allowed directories.

        Args:
            file_path: The path of the file to open.
            mode: The mode to open the file in.
            **kwargs: Additional keyword arguments for open().

        Returns:
            A file object.

        Raises:
            SecurityError: If the path is outside allowed directories.
        """
        path = Path(file_path)
        resolved_path = self._get_resolved_allowed_path(path)
        return open(resolved_path, mode=mode, **kwargs)

    def read_text(self, file_path: Union[str, Path], encoding: str = "utf-8") -> str:
        """
        Read text from a file if it falls within the allowed directories.

        Args:
            file_path: The path of the file to read.
            encoding: The encoding to use.

        Returns:
            str: The contents of the file.

        Raises:
            SecurityError: If the path is outside allowed directories.
        """
        path = Path(file_path)
        resolved_path = self._get_resolved_allowed_path(path)
        return resolved_path.read_text(encoding=encoding)

    def write_text(self, file_path: Union[str, Path], data: str, encoding: str = "utf-8") -> int:
        """
        Write text to a file if it falls within the allowed directories.

        Args:
            file_path: The path of the file to write to.
            data: The text to write.
            encoding: The encoding to use.

        Returns:
            int: The number of characters written.

        Raises:
            SecurityError: If the path is outside allowed directories.
        """
        path = Path(file_path)
        resolved_path = self._get_resolved_allowed_path(path)
        return resolved_path.write_text(data, encoding=encoding)
