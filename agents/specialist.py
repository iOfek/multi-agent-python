from typing import Annotated, List, Optional
import logging
from pydantic import Field
from livekit.plugins import openai
from livekit.agents.llm import function_tool

from agents.utils import load_prompt

from .base_agent import BaseAgent, RunContext, Agent
from .common_functions import to_greeter

class Specialist(BaseAgent):
    def __init__(self, basic_agent_knowledge: str) -> None:
        super().__init__(
            instructions=load_prompt("specialist_prompt.yaml"),
            tools=[
                to_greeter,
            ],
        )
        logger = logging.getLogger("specialist-example")
        logger.info(f"Specialist agent initialized with basic agent knowledge: {basic_agent_knowledge}")
        self.basic_agent_knowledge = basic_agent_knowledge

    @function_tool()
    async def to_adhd_specialist(self, context: RunContext) -> tuple[Agent, str]:
        """נקרא כאשר המשתמש מתאר הפרעת קשב וריכוז (ADHD)."""
        return await self._transfer_to_agent("adhd_specialist", context)
    
    @function_tool()
    async def to_psyche_specialist(self, context: RunContext) -> tuple[Agent, str]:
        """נקרא כאשר המשתמש מתאר מצב פסיכיאטרי (חרדה, דיכאון, PTSD, OCD)."""
        return await self._transfer_to_agent("psyche_specialist", context)
    
    @function_tool()
    async def to_migrain_specialist(self, context: RunContext) -> tuple[Agent, str]:
        """נקרא כאשר המשתמש מתאר מיגרנות."""
        return await self._transfer_to_agent("migraine_specialist", context)
    
    @function_tool()
    async def to_fibro_specialist(self, context: RunContext) -> tuple[Agent, str]:
        """נקרא כאשר המשתמש מתאר קרוהן/קוליטיס/פיברומיאלגיה."""
        return await self._transfer_to_agent("fibro_specialist", context)

