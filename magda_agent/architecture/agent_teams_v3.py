import asyncio
import logging
import os
import shutil
import uuid
from typing import Optional, List, Dict, Any

class GitWorktreeError(Exception):
    """Exception raised for errors during git worktree operations."""
    pass

class AgentWorktreeIsolationV3:
    """
    Manages isolated git worktrees for individual sub-agents.
    Provides isolation logic so multiple sub-agents can work without cross-contamination.
    """

    def __init__(self, base_dir: str = "/tmp/magda_agent_teams_v3") -> None:
        """
        Initialize the isolation manager.

        Args:
            base_dir (str): Base directory where worktrees will be created.
        """
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self.active_worktrees: Dict[str, str] = {}

    async def create_worktree(self, agent_id: str, branch_name: Optional[str] = None) -> str:
        """
        Creates an isolated git worktree for an agent.

        Args:
            agent_id (str): A unique identifier for the agent.
            branch_name (Optional[str]): A branch name to create for the agent, defaults to detached HEAD.

        Returns:
            str: Path to the newly created worktree.
        """
        unique_suffix = str(uuid.uuid4())[:8]
        env_path = os.path.join(self.base_dir, f"agent_{agent_id}_{unique_suffix}")

        if branch_name:
            cmd = ["git", "worktree", "add", "-b", branch_name, env_path, "HEAD"]
        else:
            cmd = ["git", "worktree", "add", "-d", env_path, "HEAD"]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                logging.error(f"Failed to create git worktree: {error_msg}")
                raise GitWorktreeError(f"Git worktree creation failed: {error_msg}")

            logging.info(f"Agent {agent_id} worktree created at {env_path}")
            self.active_worktrees[agent_id] = env_path
            return env_path
        except Exception as e:
            logging.error(f"Error during worktree creation for {agent_id}: {e}")
            raise

    async def remove_worktree(self, agent_id: str) -> None:
        """
        Removes the git worktree associated with an agent.

        Args:
            agent_id (str): The unique identifier of the agent.
        """
        env_path = self.active_worktrees.get(agent_id)
        if not env_path:
            logging.warning(f"No active worktree found for agent {agent_id}")
            return

        cmd = ["git", "worktree", "remove", "--force", env_path]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                logging.error(f"Failed to cleanly remove git worktree for {agent_id}: {stderr.decode().strip()}")
            else:
                logging.info(f"Successfully removed worktree for {agent_id}")
        except Exception as e:
            logging.error(f"Error removing worktree for {agent_id}: {e}")
        finally:
            if os.path.exists(env_path):
                try:
                    shutil.rmtree(env_path)
                except Exception as ex:
                    logging.error(f"Could not delete worktree folder for {agent_id}: {ex}")
            self.active_worktrees.pop(agent_id, None)


class AgentTeamManagerV3:
    """
    Coordinates a team of agents operating in isolated worktrees.
    """

    def __init__(self, isolation_manager: Optional[AgentWorktreeIsolationV3] = None) -> None:
        """
        Initialize the Agent Team Manager.

        Args:
            isolation_manager (Optional[AgentWorktreeIsolationV3]): Worktree isolation manager to use.
        """
        self.isolation_manager = isolation_manager or AgentWorktreeIsolationV3()
        self.agents: List[str] = []

    async def spawn_agent(self, agent_id: str, branch_name: Optional[str] = None) -> str:
        """
        Spawns a new agent and sets up its isolated worktree.

        Args:
            agent_id (str): A unique string identifying the agent.
            branch_name (Optional[str]): Branch for the worktree.

        Returns:
            str: Path to the agent's worktree.
        """
        if agent_id in self.agents:
            raise ValueError(f"Agent {agent_id} already exists.")

        worktree_path = await self.isolation_manager.create_worktree(agent_id, branch_name)
        self.agents.append(agent_id)
        return worktree_path

    async def disband_agent(self, agent_id: str) -> None:
        """
        Disbands an agent and cleans up its worktree.

        Args:
            agent_id (str): The identifier of the agent to disband.
        """
        if agent_id not in self.agents:
            logging.warning(f"Cannot disband unknown agent {agent_id}")
            return

        await self.isolation_manager.remove_worktree(agent_id)
        self.agents.remove(agent_id)

    async def disband_all(self) -> None:
        """
        Disbands all active agents and cleans up their worktrees.
        """
        agents_to_disband = list(self.agents)
        for agent_id in agents_to_disband:
            await self.disband_agent(agent_id)

    def get_active_agents(self) -> List[str]:
        """
        Returns a list of currently active agent identifiers.

        Returns:
            List[str]: The active agents.
        """
        return list(self.agents)

    def get_worktree_path(self, agent_id: str) -> Optional[str]:
        """
        Retrieves the worktree path for a specific agent if it exists.

        Args:
            agent_id (str): The unique string identifying the agent.

        Returns:
            Optional[str]: The worktree path or None.
        """
        if agent_id not in self.agents:
            return None
        return self.isolation_manager.active_worktrees.get(agent_id)

class AgentEvaluatorTeam:
    """
    Subagent evaluator pool that can test generator team code iteratively.
    Inspired by Claude Agent SDK trend.
    """
    def __init__(self, evaluators: List[str]):
        """
        Initialize the evaluator team.
        """
        self.evaluators = evaluators

    async def evaluate_code(self, code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate generator code iteratively.
        """
        results = []
        for evaluator in self.evaluators:
            result = await self._call_llm_evaluator(evaluator, code, context)
            results.append(result)

        passed = all(r.get("passed", False) for r in results)

        return {
            "passed": passed,
            "results": results,
            "overall_score": sum(r.get("score", 0) for r in results) / len(results) if results else 0
        }

    async def _call_llm_evaluator(self, evaluator_id: str, code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call the LLM for evaluation.
        """
        from magda_agent.llm_client import LLMClient
        client = LLMClient()
        prompt = f"Evaluate this code:\n{code}\nContext: {context}\nEvaluator ID: {evaluator_id}"

        response = await client.generate(prompt=prompt, system_prompt="You are a code evaluator.")

        # Simplified response parsing
        return {
            "evaluator_id": evaluator_id,
            "passed": "PASSED" in response,
            "score": 100 if "PASSED" in response else 50,
            "feedback": response
        }
