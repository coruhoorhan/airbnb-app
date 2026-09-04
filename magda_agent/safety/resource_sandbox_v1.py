"""
Hermes Portal Resource-Bounded Skill Sandbox.

Provides a lightweight subagent execution sandbox wrapper that restricts CPU
execution time, memory usage, and file descriptors to enforce resource safety boundaries.
"""

import multiprocessing
import multiprocessing.queues
import queue as builtin_queue
import time
from typing import Callable, Any, Tuple, Dict, Optional

try:
    import resource
except ImportError:
    resource = None


def _sandbox_worker(q: multiprocessing.queues.Queue, max_cpu: int, max_mem: int, max_fd: int, f: Callable, a: tuple, kw: dict) -> None:
    """
    Worker function to execute the target function within a resource-bounded process.
    """
    if resource:
        try:
            # CPU time limit (soft and hard limits)
            resource.setrlimit(resource.RLIMIT_CPU, (max_cpu, max_cpu))
            # Memory limit (RSS)
            mem_bytes = max_mem * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
            # File Descriptors limit
            _, hard_fd = resource.getrlimit(resource.RLIMIT_NOFILE)
            safe_fd = min(max_fd, hard_fd)
            resource.setrlimit(resource.RLIMIT_NOFILE, (safe_fd, safe_fd))
        except (ValueError, OSError):
            pass

    try:
        res = f(*a, **kw)
        q.put(("success", res))
    except Exception as e:
        q.put(("error", e))

class ResourceSandboxV1:
    """
    A sandbox wrapper that restricts CPU execution time, memory usage, and file descriptors.
    """

    def __init__(self, max_cpu_time: int = 5, max_memory_mb: int = 256, max_file_descriptors: int = 256) -> None:
        """
        Initialize the resource sandbox.

        Args:
            max_cpu_time (int): Maximum CPU time in seconds.
            max_memory_mb (int): Maximum memory in megabytes.
            max_file_descriptors (int): Maximum number of file descriptors.
        """
        self.max_cpu_time = max_cpu_time
        self.max_memory_mb = max_memory_mb
        self.max_file_descriptors = max_file_descriptors

    def execute(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Execute the function within a resource-bounded process.

        Args:
            func: The target function to execute.
            args: Positional arguments for the function.
            kwargs: Keyword arguments for the function.

        Raises:
            TimeoutError: If the execution time exceeds the limits.
            Exception: Whatever exception the function raised or a RuntimeError if process crashes.
        """
        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue()

        p = ctx.Process(target=_sandbox_worker, args=(queue, self.max_cpu_time, self.max_memory_mb, self.max_file_descriptors, func, args, kwargs))
        p.start()

        try:
            status, result = queue.get(timeout=self.max_cpu_time)
        except builtin_queue.Empty:
            if p.is_alive():
                p.terminate()
                p.join()
                raise TimeoutError("Sandbox execution exceeded CPU time limit.")
            else:
                raise RuntimeError(f"Sandbox execution failed to return a result (exit code {p.exitcode}).")

        p.join()

        if status == "success":
            return result
        else:
            raise result
