"""
Module for provisioning isolated virtual workspace environments.
Inspired by the Claude Agent Teams trend.
"""

import os
import tempfile
import contextlib
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def provision_isolated_workspace() -> AsyncGenerator[str, None]:
    """
    Provisions a temporary, isolated workspace directory.

    Yields the path to the newly created directory and automatically
    cleans it up when the context exits. This context manager does *not*
    modify the process-wide current working directory (os.chdir), which is
    unsafe in concurrent asyncio applications. Calling code should use the
    yielded path explicitly for all file operations.

    Yields:
        str: The path to the temporary isolated directory.
    """
    temp_dir_manager = tempfile.TemporaryDirectory()
    temp_dir = temp_dir_manager.name
    logger.debug(f"Provisioned isolated workspace at {temp_dir}")
    try:
        yield temp_dir
    finally:
        temp_dir_manager.cleanup()
        logger.debug(f"Cleaned up isolated workspace at {temp_dir}")
