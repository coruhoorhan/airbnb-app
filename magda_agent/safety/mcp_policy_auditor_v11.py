from typing import Any, Dict, List, Union

class MCPPolicyAuditorV11:
    """
    Auditor component that periodically reviews the AuditTrail or MCPAuditTrailV1
    for any blocked MCP action tool calls and generates a report of potential
    policy misconfigurations.
    """

    def __init__(self, audit_trail: Any) -> None:
        """
        Initializes the auditor with a trail instance.

        Args:
            audit_trail: An instance of AuditTrail or MCPAuditTrailV1.
        """
        self.audit_trail = audit_trail

    def audit_blocked_calls(self) -> str:
        """
        Reviews the audit logs and generates a markdown-formatted report of
        blocked MCP action tool calls.

        Returns:
            A string containing the formatted markdown report.
        """
        logs = []
        if hasattr(self.audit_trail, "get_mcp_logs"):
            logs = self.audit_trail.get_mcp_logs()
        elif hasattr(self.audit_trail, "get_all"):
            logs = self.audit_trail.get_all()
        else:
            raise ValueError("Unsupported audit trail type. Must have 'get_mcp_logs' or 'get_all' method.")

        blocked_calls = []
        for log in logs:
            is_blocked = False
            result = log.get("result", "")
            status = log.get("status", "")
            why = log.get("why", "")

            # Look for block indicators in strings
            if isinstance(result, str) and any(keyword in result.lower() for keyword in ["blocked", "denied", "reject"]):
                is_blocked = True
            if isinstance(status, str) and any(keyword in status.lower() for keyword in ["error", "blocked", "denied"]):
                is_blocked = True
            if isinstance(why, str) and any(keyword in why.lower() for keyword in ["policy violation", "blocked"]):
                is_blocked = True

            # In standard AuditTrail, sometimes result is dict with error status or similar, but
            # according to requirements, we check string indicators.
            if isinstance(result, dict):
                res_str = str(result).lower()
                if any(keyword in res_str for keyword in ["blocked", "denied", "reject", "error"]):
                    is_blocked = True

            if is_blocked:
                blocked_calls.append(log)

        if not blocked_calls:
            return "## MCP Policy Audit Report\n\nNo blocked calls found."

        report_lines = [
            "## MCP Policy Audit Report",
            "",
            f"**Total Blocked Calls:** {len(blocked_calls)}",
            "",
            "### Breakdown by Tool:"
        ]

        tool_counts: Dict[str, int] = {}
        for call in blocked_calls:
            t_name = call.get("tool_name", "unknown")
            tool_counts[t_name] = tool_counts.get(t_name, 0) + 1

        for t_name, count in sorted(tool_counts.items(), key=lambda item: item[1], reverse=True):
            report_lines.append(f"- **{t_name}**: {count} blocked attempt(s)")

        return "\n".join(report_lines)
