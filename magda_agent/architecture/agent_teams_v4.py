import asyncio
import logging
import os
import shutil
import uuid
import time
from typing import Optional, List, Dict, Tuple, Any


class GitWorktreeError(Exception):
    """Exception raised for errors during git worktree operations."""
    pass


class AgentWorktreeIsolationV4:
    """
    Manages isolated git worktrees for individual sub-agents with aggressive cleanup.
    Provides isolation logic so multiple sub-agents can work without cross-contamination.
    """

    def __init__(self, base_dir: str = "/tmp/magda_agent_teams_v4") -> None:
        """
        Initialize the isolation manager.

        Args:
            base_dir (str): Base directory where worktrees will be created.
        """
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self.active_worktrees: Dict[str, str] = {}

    async def create_worktree(self, agent_id: str, branch_name: Optional[str] = None) -> Tuple[str, Dict[str, str]]:
        """
        Creates an isolated git worktree for an agent and returns isolated environment variables.

        Args:
            agent_id (str): A unique identifier for the agent.
            branch_name (Optional[str]): A branch name to create for the agent, defaults to detached HEAD.

        Returns:
            Tuple[str, Dict[str, str]]: Path to the newly created worktree and its isolated environment variables.
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

            # Create isolated environment variables
            isolated_env = os.environ.copy()
            isolated_env["MAGDA_AGENT_ID"] = agent_id
            isolated_env["MAGDA_WORKTREE_PATH"] = env_path
            isolated_env["MAGDA_ISOLATED"] = "true"

            return env_path, isolated_env
        except Exception as e:
            logging.error(f"Error during worktree creation for {agent_id}: {e}")
            raise

    async def remove_worktree(self, agent_id: str) -> None:
        """
        Removes the git worktree associated with an agent with aggressive cleanup fallback.

        Args:
            agent_id (str): The unique identifier of the agent.
        """
        env_path = self.active_worktrees.get(agent_id)
        if not env_path:
            logging.warning(f"No active worktree found for agent {agent_id}")
            return

        cmd = ["git", "worktree", "remove", "--force", env_path]
        git_success = False
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
                git_success = True
        except Exception as e:
            logging.error(f"Error executing git worktree remove for {agent_id}: {e}")
        finally:
            if os.path.exists(env_path):
                logging.warning(f"Worktree path {env_path} still exists. Attempting aggressive cleanup.")
                await self._aggressive_cleanup(env_path)
            self.active_worktrees.pop(agent_id, None)

    async def _aggressive_cleanup(self, env_path: str, retries: int = 3, delay: float = 1.0) -> None:
        """
        Aggressively removes a directory with retries.

        Args:
            env_path (str): The path to remove.
            retries (int): Number of retries.
            delay (float): Delay between retries.
        """
        for attempt in range(retries):
            try:
                shutil.rmtree(env_path, ignore_errors=True)
                if not os.path.exists(env_path):
                    logging.info(f"Aggressive cleanup succeeded for {env_path}")
                    return
            except Exception as ex:
                logging.error(f"Attempt {attempt + 1}: Aggressive cleanup failed for {env_path}: {ex}")

            if attempt < retries - 1:
                await asyncio.sleep(delay)

        logging.error(f"Aggressive cleanup failed for {env_path} after {retries} attempts.")

class AgentTeamManagerV4:
    """
    Coordinates a team of agents operating in isolated worktrees with aggressive cleanup.
    """

    def __init__(self, isolation_manager: Optional[AgentWorktreeIsolationV4] = None) -> None:
        """
        Initialize the Agent Team Manager.

        Args:
            isolation_manager (Optional[AgentWorktreeIsolationV4]): Worktree isolation manager to use.
        """
        self.isolation_manager = isolation_manager or AgentWorktreeIsolationV4()
        self.agents: List[str] = []
        self.agent_envs: Dict[str, Dict[str, str]] = {}

    async def spawn_agent(self, agent_id: str, branch_name: Optional[str] = None) -> Tuple[str, Dict[str, str]]:
        """
        Spawns a new agent and sets up its isolated worktree.

        Args:
            agent_id (str): A unique string identifying the agent.
            branch_name (Optional[str]): Branch for the worktree.

        Returns:
            Tuple[str, Dict[str, str]]: Path to the agent's worktree and its isolated environment.
        """
        if agent_id in self.agents:
            raise ValueError(f"Agent {agent_id} already exists.")

        worktree_path, isolated_env = await self.isolation_manager.create_worktree(agent_id, branch_name)
        self.agents.append(agent_id)
        self.agent_envs[agent_id] = isolated_env
        return worktree_path, isolated_env

    def get_agent_env(self, agent_id: str) -> Optional[Dict[str, str]]:
        """
        Retrieves the isolated environment for a spawned agent.

        Args:
            agent_id (str): A unique string identifying the agent.

        Returns:
            Optional[Dict[str, str]]: The isolated environment dictionary, if agent exists.
        """
        return self.agent_envs.get(agent_id)

    async def disband_agent(self, agent_id: str) -> None:
        """
        Disbands an agent and aggressively cleans up its worktree.

        Args:
            agent_id (str): The identifier of the agent to disband.
        """
        if agent_id not in self.agents:
            logging.warning(f"Cannot disband unknown agent {agent_id}")
            return

        await self.isolation_manager.remove_worktree(agent_id)
        self.agents.remove(agent_id)
        self.agent_envs.pop(agent_id, None)

    async def disband_all(self) -> None:
        """
        Disbands all active agents and aggressively cleans up their worktrees.
        """
        agents_to_disband = list(self.agents)
        for agent_id in agents_to_disband:
            await self.disband_agent(agent_id)

class AgentEvaluatorTeamV4:
    """
    Subagent evaluator pool that can test generator team code iteratively with strict sandboxing.
    Inspired by Claude Agent SDK trend.
    """

    def __init__(self, evaluators: List[str], team_manager: Optional[AgentTeamManagerV4] = None) -> None:
        """
        Initialize the evaluator team.

        Args:
            evaluators (List[str]): The list of evaluator IDs.
            team_manager (Optional[AgentTeamManagerV4]): Manager for strict sandboxing.
        """
        self.evaluators = evaluators
        self.team_manager = team_manager or AgentTeamManagerV4()

    async def evaluate_code(self, code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate generator code iteratively within strict sandboxes.

        Args:
            code (str): The code to evaluate.
            context (Dict[str, Any]): Additional context.

        Returns:
            Dict[str, Any]: The evaluation results.
        """
        results = []
        for evaluator in self.evaluators:
            # Sandbox setup
            try:
                worktree_path, isolated_env = await self.team_manager.spawn_agent(evaluator)
            except ValueError:
                # If already spawned, get the environment
                isolated_env = self.team_manager.get_agent_env(evaluator) or {}

            try:
                result = await self._call_llm_evaluator(evaluator, code, context, isolated_env)
                results.append(result)
            finally:
                # Ensure teardown for strict sandboxing
                await self.team_manager.disband_agent(evaluator)

        passed = bool(results) and all(r.get("passed", False) for r in results)

        return {
            "passed": passed,
            "results": results,
            "overall_score": sum(r.get("score", 0) for r in results) / len(results) if results else 0.0
        }

    async def _call_llm_evaluator(self, evaluator_id: str, code: str, context: Dict[str, Any], isolated_env: Dict[str, str]) -> Dict[str, Any]:
        """
        Call the LLM for evaluation.

        Args:
            evaluator_id (str): Evaluator identifier.
            code (str): The code to evaluate.
            context (Dict[str, Any]): Additional context.
            isolated_env (Dict[str, str]): Environment details from sandbox.

        Returns:
            Dict[str, Any]: Evaluation result parsed from LLM response.
        """
        from magda_agent.llm_client import LLMClient
        client = LLMClient()
        prompt = f"Evaluate this code:\n{code}\nContext: {context}\nEvaluator ID: {evaluator_id}\nSandbox: {isolated_env.get('MAGDA_WORKTREE_PATH')}"

        response = await client.generate(prompt=prompt)

        return {
            "evaluator_id": evaluator_id,
            "passed": "PASSED" in response,
            "score": 100 if "PASSED" in response else 50,
            "feedback": response
        }
