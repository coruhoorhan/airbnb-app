"""
MCP Action Tools Export Compatibility V2 (V8 Exporter).

Inspired by the Model Context Protocol (MCP) standard: Enables native export
of Python functions, coroutines, and SkillRegistry skills into standardized
MCP tool definitions with rich JSON schemas, type mappings, and parameter descriptions.
"""

import asyncio
import inspect
import json
import logging
import re
import types
from dataclasses import asdict, dataclass, field
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
    get_args,
    get_origin,
)

logger = logging.getLogger(__name__)


@dataclass
class MCPToolDefinitionV8:
    """Represents a standardized MCP Tool Definition according to MCP 2024+ specifications."""

    name: str
    description: str
    inputSchema: Dict[str, Any] = field(default_factory=dict)
    outputSchema: Optional[Dict[str, Any]] = None
    category: str = "action"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.inputSchema,
        }
        if self.outputSchema:
            d["outputSchema"] = self.outputSchema
        if self.category:
            d["category"] = self.category
        if self.metadata:
            d["metadata"] = self.metadata
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class MCPToolSchemaExtractorV8:
    """Extracts JSON Schema from Python callable signatures and docstrings."""

    TYPE_MAP = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        dict: "object",
        list: "array",
        set: "array",
        tuple: "array",
        bytes: "string",
    }

    @classmethod
    def _parse_docstring_params(cls, doc: Optional[str]) -> Tuple[str, Dict[str, str]]:
        """Extract function summary and parameter descriptions from docstrings."""
        if not doc:
            return "", {}

        lines = [l.strip() for l in doc.strip().split("\n")]
        summary = lines[0] if lines else ""
        param_docs: Dict[str, str] = {}

        # Matches :param name: desc or Args: \n name: desc
        param_pattern = re.compile(r"^(?:(?:-\s*)?(\w+)\s*(?:\([^)]*\))?\s*:\s*|:param\s+(\w+)\s*:\s*)(.+)$")

        for line in lines[1:]:
            m = param_pattern.match(line)
            if m:
                pname = m.group(1) or m.group(2)
                pdesc = m.group(3)
                if pname and pdesc:
                    param_docs[pname.strip()] = pdesc.strip()

        return summary, param_docs

    @classmethod
    def _python_type_to_json_schema(cls, py_type: Any) -> Dict[str, Any]:
        """Convert a Python type annotation to a JSON Schema fragment."""
        if py_type in (inspect.Parameter.empty, Any, None):
            return {"type": "string"}

        origin = get_origin(py_type)
        args = get_args(py_type)

        # Handle Optional[T] / Union[T, None]
        if origin is Union or origin is getattr(types, "UnionType", None):
            # Filter out NoneType
            non_none_args = [a for a in args if a not in (type(None), None)]
            if len(non_none_args) == 1:
                return cls._python_type_to_json_schema(non_none_args[0])
            return {
                "anyOf": [cls._python_type_to_json_schema(a) for a in non_none_args]
            }

        # Handle List[T] / Set[T]
        if origin in (list, set, tuple, List, Set, Tuple):
            item_schema = cls._python_type_to_json_schema(args[0]) if args else {"type": "string"}
            return {"type": "array", "items": item_schema}

        # Handle Dict[K, V]
        if origin in (dict, Dict):
            val_schema = cls._python_type_to_json_schema(args[1]) if len(args) > 1 else {"type": "string"}
            return {"type": "object", "additionalProperties": val_schema}

        # Direct type lookup
        if py_type in cls.TYPE_MAP:
            return {"type": cls.TYPE_MAP[py_type]}

        return {"type": "string"}

    @classmethod
    def generate_schema(
        cls,
        func: Callable[..., Any],
        name_override: Optional[str] = None,
        desc_override: Optional[str] = None,
    ) -> MCPToolDefinitionV8:
        """Inspect callable and produce an MCPToolDefinitionV8."""
        name = name_override or getattr(func, "__name__", "unnamed_tool")
        doc = getattr(func, "__doc__", "")
        doc_summary, param_docs = cls._parse_docstring_params(doc)
        description = desc_override or doc_summary or f"Executes the {name} action tool."

        sig = inspect.signature(func)
        properties: Dict[str, Any] = {}
        required: List[str] = []

        for param_name, param in sig.parameters.items():
            # Skip *args and **kwargs
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue

            param_schema = cls._python_type_to_json_schema(param.annotation)

            # Add doc description if available
            if param_name in param_docs:
                param_schema["description"] = param_docs[param_name]

            # Add default value if present
            if param.default is not inspect.Parameter.empty:
                param_schema["default"] = param.default
            else:
                required.append(param_name)

            properties[param_name] = param_schema

        input_schema = {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }

        # Return type schema
        output_schema = None
        if sig.return_annotation is not inspect.Signature.empty and sig.return_annotation not in (None, type(None)):
            output_schema = cls._python_type_to_json_schema(sig.return_annotation)

        return MCPToolDefinitionV8(
            name=name,
            description=description,
            inputSchema=input_schema,
            outputSchema=output_schema,
        )


class MCPActionToolsExporterV8:
    """
    Exports registered skills and functions into MCP compatible tool definitions.
    """

    def __init__(self, server_name: str = "magda-agent-tools", version: str = "1.0.0"):
        self.server_name = server_name
        self.version = version

    def export_callable(
        self,
        func: Callable[..., Any],
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> MCPToolDefinitionV8:
        """Export a single callable into MCPToolDefinitionV8."""
        return MCPToolSchemaExtractorV8.generate_schema(func, name_override=name, desc_override=description)

    def export_skills(
        self,
        skills_map: Dict[str, Callable[..., Any]],
        descriptions: Optional[Dict[str, str]] = None,
    ) -> List[MCPToolDefinitionV8]:
        """Export a dictionary of skill name -> function mappings."""
        descs = descriptions or {}
        exported = []
        for name, func in skills_map.items():
            d = descs.get(name)
            tool_def = self.export_callable(func, name=name, description=d)
            exported.append(tool_def)
        return exported

    def export_skill_registry(self, registry: Any) -> List[MCPToolDefinitionV8]:
        """Extract and export all tools from a SkillRegistry instance."""
        skills: Dict[str, Callable[..., Any]] = {}
        descriptions: Dict[str, str] = {}

        if hasattr(registry, "skills") and isinstance(registry.skills, dict):
            skills = registry.skills
            if hasattr(registry, "descriptions") and isinstance(registry.descriptions, dict):
                descriptions = registry.descriptions
        elif hasattr(registry, "get_all_skills"):
            skills = registry.get_all_skills()
        elif hasattr(registry, "list_skills"):
            for s in registry.list_skills():
                if hasattr(registry, "get_skill"):
                    skills[s] = registry.get_skill(s)

        return self.export_skills(skills, descriptions)

    def generate_mcp_manifest(
        self,
        tools: List[MCPToolDefinitionV8],
    ) -> Dict[str, Any]:
        """Generate a full MCP server tool manifest."""
        return {
            "server": {
                "name": self.server_name,
                "version": self.version,
            },
            "protocol_version": "2024-11-05",
            "tools": [t.to_dict() for t in tools],
        }

    def export_to_json(
        self,
        tools: List[MCPToolDefinitionV8],
        indent: int = 2,
    ) -> str:
        """Produce JSON manifest representation of tools."""
        manifest = self.generate_mcp_manifest(tools)
        return json.dumps(manifest, indent=indent)
