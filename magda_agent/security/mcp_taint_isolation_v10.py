"""
MCPKernel Tool Taint Isolation V10.

Implements strict process-level network isolation for subprocesses
that execute external tools utilizing tainted user data.
"""
import ctypes
import os
import subprocess
from typing import Any, Dict, List, Optional, Union

from magda_agent.security.mcp_kernel_taint import is_tainted, sanitize

# Linux CLONE_NEWNET flag for unshare syscall
CLONE_NEWNET = 0x40000000

class IsolationError(Exception):
    """Exception raised when network isolation cannot be guaranteed."""
    pass


def _drop_network() -> None:
    """
    Attempts to drop network access using the Linux unshare syscall.
    If the system call fails (e.g., due to lack of CAP_SYS_ADMIN privileges
    or being on a non-Linux platform), it raises an IsolationError to fail securely.
    """
    try:
        libc = ctypes.CDLL("libc.so.6")
        result = libc.unshare(CLONE_NEWNET)
        if result != 0:
            raise IsolationError(f"Failed to drop network access: unshare returned {result}")
    except OSError as e:
        raise IsolationError(f"Failed to drop network access: {e}")
    except AttributeError:
        raise IsolationError("Failed to drop network access: libc.so.6 not found or unshare not supported")


class IsolatedSubprocessProxy:
    """
    A proxy for executing subprocesses with network isolation for tainted data.
    """

    @staticmethod
    def run(
        args: Union[str, List[Any]],
        env: Optional[Dict[str, str]] = None,
        **kwargs: Any
    ) -> subprocess.CompletedProcess:
        """
        Executes a command. If any arguments or environment variables are tainted,
        applies strict network isolation.

        Args:
            args: The command and its arguments.
            env: Optional environment variables dictionary.
            **kwargs: Additional keyword arguments for subprocess.run.

        Returns:
            The CompletedProcess instance resulting from the execution.

        Raises:
            IsolationError: If tainted data is detected but isolation fails.
        """
        has_taint = is_tainted(args) or (env is not None and is_tainted(env))

        # Sanitize arguments and environment to avoid type issues with subprocess.run
        clean_args = sanitize(args)
        clean_env = sanitize(env)

        execution_env = clean_env.copy() if clean_env is not None else os.environ.copy()

        # Isolate if tainted
        preexec_fn = kwargs.get("preexec_fn")

        if has_taint:
            # Set environment flag for mocked testing or downstream wrappers
            execution_env["__MCP_ISOLATED_NETWORK"] = "1"

            # Use unshare to drop network access on Linux. Must fail if unsuccessful.
            def _isolated_preexec() -> None:
                _drop_network()
                if preexec_fn is not None:
                    preexec_fn()

            kwargs["preexec_fn"] = _isolated_preexec

        kwargs["env"] = execution_env

        return subprocess.run(clean_args, **kwargs)
