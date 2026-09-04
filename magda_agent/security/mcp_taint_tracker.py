"""
MCPKernel Taint Tracking Module.
Implements a mechanism to track data flow from external MCP tools to prevent
prompt injection and unauthorized state mutation.
"""
from typing import Any, List, Union, Tuple, Set


class TaintError(Exception):
    """Exception raised when a taint violation occurs."""
    pass


class TaintedString(str):
    """
    A string wrapper that carries taint information.
    """

    def __new__(cls, value: str, taints: Set[str] = None) -> 'TaintedString':
        """Creates a new TaintedString instance."""
        obj = str.__new__(cls, value)
        obj.taints = set(taints) if taints else set()
        return obj

    def __add__(self, other: Union[str, 'TaintedString']) -> 'TaintedString':
        """Adds another string to this one, combining taints."""
        combined_taints = set(self.taints)
        if isinstance(other, TaintedString):
            combined_taints.update(other.taints)
        return TaintedString(str(self) + str(other), combined_taints)

    def __radd__(self, other: Union[str, 'TaintedString']) -> 'TaintedString':
        """Right-adds another string to this one, combining taints."""
        combined_taints = set(self.taints)
        if isinstance(other, TaintedString):
            combined_taints.update(other.taints)
        return TaintedString(str(other) + str(self), combined_taints)

    def __mul__(self, count: int) -> 'TaintedString':
        """Multiplies the string, propagating taints."""
        return TaintedString(str(self) * count, self.taints)

    def __rmul__(self, count: int) -> 'TaintedString':
        """Right-multiplies the string, propagating taints."""
        return TaintedString(str(self) * count, self.taints)

    def join(self, iterable: Any) -> 'TaintedString':
        """Joins an iterable of strings, collecting all taints."""
        result_str = str(self).join(str(item) for item in iterable)
        combined_taints = set(self.taints)
        for item in iterable:
            if isinstance(item, TaintedString):
                combined_taints.update(item.taints)
        return TaintedString(result_str, combined_taints)

    def replace(self, old: str, new: str, count: int = -1) -> 'TaintedString':
        """Replaces a substring, collecting taints from the arguments."""
        combined_taints = set(self.taints)
        if isinstance(old, TaintedString):
            combined_taints.update(old.taints)
        if isinstance(new, TaintedString):
            combined_taints.update(new.taints)
        return TaintedString(str(self).replace(str(old), str(new), count), combined_taints)

    def format(self, *args: Any, **kwargs: Any) -> 'TaintedString':
        """Formats the string, collecting taints from the formatting arguments."""
        combined_taints = set(self.taints)
        for arg in args:
            if isinstance(arg, TaintedString):
                combined_taints.update(arg.taints)
        for val in kwargs.values():
            if isinstance(val, TaintedString):
                combined_taints.update(val.taints)

        # Clean arguments for the actual formatting to avoid recursive taint checks
        # or formatting issues with subclasses of str
        clean_args = [str(arg) if isinstance(arg, TaintedString) else arg for arg in args]
        clean_kwargs = {k: str(v) if isinstance(v, TaintedString) else v for k, v in kwargs.items()}

        return TaintedString(str(self).format(*clean_args, **clean_kwargs), combined_taints)

    # Additional string methods can be overridden to propagate taints


class MCPTaintTracker:
    """
    Tracks and manages data originating from external MCP tools.
    """
    def __init__(self) -> None:
        """Initializes the Taint Tracker."""
        self._sensitive_endpoints = set()

    def register_sensitive_endpoint(self, endpoint_name: str) -> None:
        """
        Registers an endpoint as sensitive.

        Args:
            endpoint_name: The name of the endpoint to protect.
        """
        self._sensitive_endpoints.add(endpoint_name)

    def label_data(self, data: str, source: str) -> TaintedString:
        """
        Labels data with a taint source.

        Args:
            data: The string data to taint.
            source: The source of the taint (e.g., 'mcp_tool_x').

        Returns:
            A TaintedString with the specified source.
        """
        return TaintedString(data, taints={source})

    def check_execution(self, endpoint_name: str, data: Any) -> None:
        """
        Checks if tainted data is attempting to reach a sensitive endpoint.

        Args:
            endpoint_name: The name of the endpoint being accessed.
            data: The data being passed to the endpoint.

        Raises:
            TaintError: If tainted data reaches a sensitive endpoint.
        """
        if endpoint_name in self._sensitive_endpoints:
            if isinstance(data, TaintedString) and data.taints:
                raise TaintError(f"Tainted data from {data.taints} attempted to access sensitive endpoint '{endpoint_name}'")
            # If data is a dictionary, list, etc., we would recursively check for TaintedString
            elif isinstance(data, (list, tuple, set)):
                for item in data:
                    self.check_execution(endpoint_name, item)
            elif isinstance(data, dict):
                for key, value in data.items():
                    self.check_execution(endpoint_name, key)
                    self.check_execution(endpoint_name, value)
