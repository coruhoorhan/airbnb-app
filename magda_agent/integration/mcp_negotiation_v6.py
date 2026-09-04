from typing import Dict, Any, List, Optional

class CapabilityRejectedError(Exception):
    """Raised when a required capability is rejected during negotiation."""
    pass

class MCPCapabilityNegotiatorV6:
    """
    Handles multi-turn capability negotiation for MCP tools to ensure both
    client and server agree on supported features before execution.
    """

    def __init__(self, server_capabilities: Dict[str, Any]) -> None:
        """
        Initializes the negotiator with the server's supported capabilities.

        Args:
            server_capabilities: A dictionary of capabilities supported by the server.
        """
        self.server_capabilities = server_capabilities

    def negotiate(self, client_capabilities: Dict[str, Any], required_capabilities: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Negotiates capabilities between client and server.

        Args:
            client_capabilities: The capabilities requested or supported by the client.
            required_capabilities: A list of capabilities that MUST be supported by the server.

        Returns:
            A dictionary of the agreed-upon capabilities.

        Raises:
            CapabilityRejectedError: If a required capability is not supported by the server.
        """
        agreed_capabilities: Dict[str, Any] = {}

        if required_capabilities:
            for req in required_capabilities:
                if req not in self.server_capabilities:
                    raise CapabilityRejectedError(f"Required capability '{req}' is not supported by the server.")

        for cap, details in client_capabilities.items():
            if cap in self.server_capabilities:
                agreed_capabilities[cap] = details

        return agreed_capabilities

    def get_fallback_capabilities(self, client_capabilities: Dict[str, Any], fallback_map: Dict[str, str]) -> Dict[str, Any]:
        """
        Attempts to find fallback capabilities if primary ones are not supported.

        Args:
            client_capabilities: The capabilities requested by the client.
            fallback_map: A mapping from a requested capability to a fallback capability.

        Returns:
            A dictionary of capabilities including fallbacks where applicable.
        """
        agreed_capabilities: Dict[str, Any] = {}

        for cap, details in client_capabilities.items():
            if cap in self.server_capabilities:
                agreed_capabilities[cap] = details
            elif cap in fallback_map:
                fallback_cap = fallback_map[cap]
                if fallback_cap in self.server_capabilities:
                    agreed_capabilities[fallback_cap] = details

        return agreed_capabilities
