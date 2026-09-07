"""
Pre-LLM Secret Redaction Layer.

Scans prompts and messages before they leave the machine for sensitive
credentials (passwords, tokens, API keys, private connection strings)
and replaces them with reversible placeholder tokens (<SECRET_01>, etc.).
Provides restore functionality to reconstruct real credentials in tool execution.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class SecretRedactor:
    """
    Pre-LLM secret redaction engine.
    Replaces credentials and sensitive strings with reversible <SECRET_NN> tokens.
    Thread-safe and stateless.
    """

    # Priority patterns:
    # Each entry is (name, regex_pattern, group_to_mask, custom_filter_name)
    PATTERNS: list[tuple[str, re.Pattern, int | None, str | None]] = [
        # SSH / Login passwords
        (
            "SSH_PASSWORD",
            re.compile(r"(?i)\b(?:password|şifre\w*|pass(?:word)?)\s*[:=\s]\s*([^\s,;]+)"),
            1,
            None,
        ),
        # API Keys with known prefixes (Bearer token or ghp_/sk-/sk_ tokens)
        (
            "API_KEY",
            re.compile(
                r"(?i)\bBearer\s+([A-Za-z0-9_\-\.]{16,})\b|\b((?:ghp_|sk-|sk_)[A-Za-z0-9_\-]{16,})\b"
            ),
            None,
            None,
        ),
        # Generic secrets / tokens
        (
            "GENERIC_SECRET",
            re.compile(r"(?i)\b(?:secret|token|api_key)\s*[:=]\s*([^\s,;]+)"),
            1,
            None,
        ),
        # Private IPs (masked only if preceded by @ or ssh within 20 chars, or followed by :/)
        (
            "PRIVATE_IP",
            re.compile(r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3})\b"),
            1,
            "ip_filter",
        ),
    ]

    @classmethod
    def _ip_filter(cls, match: re.Match, full_text: str) -> bool:
        start, end = match.span()
        prefix = full_text[max(0, start - 20) : start]
        suffix = full_text[end : min(len(full_text), end + 5)]

        # Check if preceded by @ or ssh (case-insensitive)
        if "@" in prefix or re.search(r"(?i)\bssh\b", prefix):
            return True
        # Check if followed by :/
        if suffix.startswith(":/"):
            return True
        return False

    @classmethod
    def mask(cls, text: str) -> tuple[str, dict[str, str]]:
        """
        Scans text and replaces secrets with <SECRET_01>, <SECRET_02>, etc.
        Returns (masked_text, vault) where vault maps tokens to original secrets.
        Thread-safe and stateless.
        """
        if not text:
            return ("", {})

        try:
            spans: list[tuple[int, int, str]] = []

            for name, pattern, group_idx, filter_name in cls.PATTERNS:
                for match in pattern.finditer(text):
                    if filter_name == "ip_filter":
                        if not cls._ip_filter(match, text):
                            continue

                    if group_idx is not None:
                        secret_val = match.group(group_idx)
                        if not secret_val:
                            continue
                        m_start, m_end = match.span(group_idx)
                    else:
                        # Multi-group pattern (like API_KEY)
                        secret_val = None
                        m_start, m_end = 0, 0
                        last_idx = match.lastindex or 1
                        for g in range(1, last_idx + 1):
                            val = match.group(g)
                            if val:
                                secret_val = val
                                m_start, m_end = match.span(g)
                                break
                        if not secret_val:
                            continue

                    # Check if this span overlaps with already recorded span
                    overlap = False
                    for s, e, _ in spans:
                        if max(s, m_start) < min(e, m_end):
                            overlap = True
                            break
                    if not overlap:
                        spans.append((m_start, m_end, secret_val))

            if not spans:
                return (text, {})

            # Sort spans by start index
            spans.sort(key=lambda x: x[0])

            # Build masked text and vault
            vault: dict[str, str] = {}
            result_parts: list[str] = []
            last_idx = 0
            counter = 1

            for s_start, s_end, secret_val in spans:
                token = f"<SECRET_{counter:02d}>"
                vault[token] = secret_val
                counter += 1

                result_parts.append(text[last_idx:s_start])
                result_parts.append(token)
                last_idx = s_end

            result_parts.append(text[last_idx:])
            return ("".join(result_parts), vault)

        except Exception as exc:
            logger.warning(f"SecretRedactor.mask failed, returning original text: {exc}")
            return (text, {})

    @classmethod
    def restore(cls, text: str, vault: dict[str, str] | None) -> str:
        """
        Replaces every <SECRET_NN> token in text with its vault value.
        """
        if not text or not vault:
            return text

        try:
            result = text
            for token, val in vault.items():
                result = result.replace(token, val)
            return result
        except Exception as exc:
            logger.warning(f"SecretRedactor.restore failed, returning text as-is: {exc}")
            return text
