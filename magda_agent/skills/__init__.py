import logging
from typing import Optional, TYPE_CHECKING
from magda_agent.skills.registry import SkillRegistry

if TYPE_CHECKING:
    from magda_agent.safety.policy import PolicyLayer
from magda_agent.skills.system_execute_code import execute as code_executor
from magda_agent.skills.cloud_vm_skill import execute_in_cloud_vm
from magda_agent.skills.internet_search import search_internet
from magda_agent.skills.omnichannel import send_message as omnichannel_send
from magda_agent.skills.names import SkillNames
from magda_agent.skills.codex_worker import codex_worker
from magda_agent.skills.mcp_kernel_executor import execute as mcp_kernel_executor
from magda_agent.skills.web_navigation import web_navigate as web_navigation_skill
from magda_agent.skills.web_navigation_v2 import web_navigate_v2 as web_navigation_skill_v2


from magda_agent.skills.mcp_registry_sync_v11 import MCPRegistrySyncV11
from magda_agent.skills.mcp_registry import MCPRegistry
from magda_agent.skills.mcp_eval_v2 import MCPEvaluatorPluginV2

def initialize_skills(policy_layer: Optional["PolicyLayer"] = None) -> SkillRegistry:
    registry = SkillRegistry(policy_layer=policy_layer)

    # Register Programmer Skill
    registry.register_skill(
        name=SkillNames.PROGRAMMER,
        func=code_executor,
        description="Executes Python code in a safe sandbox. Input: 'code' string."
    )

    # Register MCP Kernel Executor Skill
    registry.register_skill(
        name="mcp_kernel_execute",
        func=mcp_kernel_executor,
        description="Executes Python code in a strictly sandboxed MCP kernel environment with taint tracking. Input: 'code' string."
    )

    # Register Cloud VM Executor Skill
    registry.register_skill(
        name=SkillNames.CLOUD_VM_EXECUTE,
        func=execute_in_cloud_vm,
        description="Executes Python code in a fully isolated Cloud VM. Use for highly sensitive or destructive tasks. Input: 'code' string."
    )

    # Register Search Skill
    registry.register_skill(
        name="internet_search",
        func=search_internet,
        description="Searches the internet for information. Input: 'query' string."
    )

    # Register Omnichannel Skill
    registry.register_skill(
        name=SkillNames.OMNICHANNEL_SEND,
        func=omnichannel_send,
        description="Sends a message to a recipient on a specified platform (telegram, whatsapp, email). Input: 'platform', 'recipient', 'message' strings."
    )

    # Register Codex Worker Skill
    registry.register_skill(
        name="codex_worker",
        func=codex_worker,
        description="Generates a Codex-ready task prompt from the project's task manifest. This is a low side-effect prompt-only capability. Input: optional 'task_id' string."
    )


    # Register Web Navigation Skill
    registry.register_skill(
        name="web_navigation",
        func=web_navigation_skill,
        description="Navigates the web by loading URLs and interacting with DOM elements. Input: 'action' string ('load', 'click', 'type') and kwargs ('url', 'element_id', 'text')."
    )


    from magda_agent.skills.experience_generator_v2 import ExperienceGeneratorV2
    from magda_agent.skills.hermes_skills import HermesSkillCreator
    from magda_agent.skills.skill_generator import SkillGenerator
    def generate_skill_sync(skill_name: str, description: str, instructions: str) -> str:
        import asyncio
        from magda_agent.llm_client import LLMClient
        client = LLMClient()
        creator = HermesSkillCreator(llm_client=client)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import threading
                result = None
                def run_in_thread():
                    nonlocal result
                    result = asyncio.run(creator.generate_skill(skill_name, description, instructions))
                t = threading.Thread(target=run_in_thread)
                t.start()
                t.join()
                return result
        except RuntimeError:
            pass
        return asyncio.run(creator.generate_skill(skill_name, description, instructions))

    def generate_skill_from_queries_sync(queries: list[str]) -> Optional[str]:
        """
        Synchronously wraps the generate_skill_from_queries coroutine.
        """
        import asyncio
        from magda_agent.llm_client import LLMClient
        client = LLMClient()
        generator = SkillGenerator(llm_client=client)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import threading
                result = None
                def run_in_thread():
                    nonlocal result
                    result = asyncio.run(generator.generate_skill_from_queries(queries))
                t = threading.Thread(target=run_in_thread)
                t.start()
                t.join()
                return result
        except RuntimeError:
            pass
        return asyncio.run(generator.generate_skill_from_queries(queries))


    def generate_skill_from_traces_sync(traces: list, skill_name: str, description: str) -> Optional[str]:
        """
        Synchronously wraps the generate_skill_from_traces coroutine.
        """
        import asyncio
        from magda_agent.llm_client import LLMClient
        client = LLMClient()
        generator = ExperienceGeneratorV2(llm_client=client)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import threading
                result = None
                def run_in_thread():
                    nonlocal result
                    result = asyncio.run(generator.generate_skill_from_traces(traces, skill_name, description))
                t = threading.Thread(target=run_in_thread)
                t.start()
                t.join()
                return result
        except RuntimeError:
            pass
        return asyncio.run(generator.generate_skill_from_traces(traces, skill_name, description))

    registry.register_skill(
        name="experience_generator_v2",
        func=generate_skill_from_traces_sync,
        description="Generates a Python skill module from a sequence of successful execution traces. Input: 'traces' list of dicts, 'skill_name' string, 'description' string."
    )

    registry.register_skill(
        name="hermes_skill_creator",
        func=generate_skill_sync,
        description="Generate Python code for a new agent skill based on experience. Input: 'skill_name', 'description', 'instructions' strings."
    )

    registry.register_skill(
        name="hermes_skill_generator",
        func=generate_skill_from_queries_sync,
        description="Generate Python code for a new agent skill based on repeated user queries. Input: 'queries' list of strings."
    )


    # Register Web Navigation V2 Skill
    registry.register_skill(
        name="web_navigation_v2",
        func=web_navigation_skill_v2,
        description="Advanced web navigation skill v2 inspired by WebArena. Provides load, click, type, scroll, and submit actions. Input: 'action' string and kwargs."
    )


    # Register MCP Auto-Discovery V1
    from magda_agent.skills.mcp_auto_discovery_v1 import MCPAutoDiscoveryV1
    from magda_agent.skills.mcp_registry_v7 import MCPRegistryV7
    mcp_registry_v7 = MCPRegistryV7()
    mcp_discoverer = MCPAutoDiscoveryV1(registry=mcp_registry_v7)

    def run_mcp_auto_discovery(directory: str) -> str:
        """Runs the auto discovery and returns the list of registered tools."""
        mcp_discoverer.discover_and_register(directory)
        return f"Discovered and registered: {mcp_registry_v7.list_tools()}"

    registry.register_skill(
        name="mcp_auto_discovery_v1",
        func=run_mcp_auto_discovery,
        description="Scans a specified directory to dynamically discover and register MCP tool schemas from Python files. Input: 'directory' string."
    )

    # Register Marketplace Sync Routine
    from magda_agent.skills.marketplace_sync import MarketplaceSyncRoutine
    def sync_marketplace_sync() -> int:
        import asyncio
        routine = MarketplaceSyncRoutine(registry=registry)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import threading
                result = None
                def run_in_thread():
                    nonlocal result
                    result = asyncio.run(routine.run_sync_cycle())
                t = threading.Thread(target=run_in_thread)
                t.start()
                t.join()
                return result
        except RuntimeError:
            pass
        return asyncio.run(routine.run_sync_cycle())

    registry.register_skill(
        name="marketplace_sync",
        func=sync_marketplace_sync,
        description="Periodically fetches and synchronizes new skills from the external agentskills.io marketplace into the agent's skill registry."
    )


    # MCP Registry Sync V11 setup
    mcp_registry_sync_registry = MCPRegistry()
    mcp_registry_sync_v11 = MCPRegistrySyncV11(registry=mcp_registry_sync_registry, mcp_server_url="http://localhost:8080")

    def sync_mcp_registry_v11() -> int:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import threading
                result = None
                def run_in_thread():
                    nonlocal result
                    result = asyncio.run(mcp_registry_sync_v11.sync_once())
                t = threading.Thread(target=run_in_thread)
                t.start()
                t.join()
                return 1
        except RuntimeError:
            pass
        asyncio.run(mcp_registry_sync_v11.sync_once())
        return 1

    registry.register_skill(
        name="mcp_registry_sync_v11",
        func=sync_mcp_registry_v11,
        description="Periodically polls a configured MCP server URL and dynamically registers or unregisters tools in the local MCPRegistry."
    )


    mcp_evaluator_v2 = MCPEvaluatorPluginV2()

    def run_mcp_evaluator_v2(tool_schema: dict, sandbox_url: str) -> dict:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import threading
                result = None
                def run_in_thread():
                    nonlocal result
                    result = asyncio.run(mcp_evaluator_v2.evaluate_skill(tool_schema, sandbox_url))
                t = threading.Thread(target=run_in_thread)
                t.start()
                t.join()
                return result
        except RuntimeError:
            pass
        return asyncio.run(mcp_evaluator_v2.evaluate_skill(tool_schema, sandbox_url))

    registry.register_skill(
        name="mcp_evaluator_v2",
        func=run_mcp_evaluator_v2,
        description="Evaluates new skills against an MCP dynamic verification sandbox. Input: 'tool_schema' dict, 'sandbox_url' string."
    )

    return registry


from magda_agent.skills.marketplace import fetch_and_register_skills
from magda_agent.skills.dynamic_generation import DynamicSkillGenerator, TrajectoryStep
