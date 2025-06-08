from typing import Annotated, List, Optional
import logging
from pydantic import Field
from livekit.plugins import openai
from livekit.agents.llm import function_tool

from agents.utils import load_prompt

from .base_agent import BaseAgent, RunContext, Agent
from .common_functions import to_greeter

class MigraineSpecialist(BaseAgent):
    def __init__(self, basic_agent_knowledge: str) -> None:
        super().__init__(
            instructions=load_prompt("migraine_specialist_prompt.yaml"),
            tools=[
                
            ],
        )
        logger = logging.getLogger("migraine-specialist-example")
        logger.info(f"Migraine specialist agent initialized with basic agent knowledge: {basic_agent_knowledge}")
        self.basic_agent_knowledge = basic_agent_knowledge

    @function_tool()
    async def ask_migraine_frequency(
        self,
        migraine_frequency: Annotated[str, Field(description="Number of migraine attacks per month")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק את תדירות ההתקפים."""
        userdata = context.userdata
        userdata.migraine_frequency = migraine_frequency
        return f"תודה על המידע. תדירות ההתקפים נרשמה."

    @function_tool()
    async def ask_medication_type(
        self,
        medication_type: Annotated[str, Field(description="Types of medications tried")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק מידע על טיפולים תרופתיים."""
        userdata = context.userdata
        userdata.medication_type = medication_type
        return f"תודה על המידע. הטיפולים התרופתיים נרשמו."

    @function_tool()
    async def ask_medical_documentation(
        self,
        medical_documentation: Annotated[str, Field(description="Whether medical documentation exists")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק מידע על תיעוד רפואי."""
        userdata = context.userdata
        userdata.medical_documentation = medical_documentation
        return f"תודה על המידע. המידע על תיעוד רפואי נרשם."

    @function_tool()
    async def to_specialist(
        self, 
        context: RunContext) -> tuple[Agent, str]:
        """נקרא כאשר המשתמש מעוניין להתעסק במומחה מיוחד."""
        userdata = context.userdata
        has_fibro = userdata.has_fibro
        has_other = userdata.has_other
        if has_fibro:
            return await self._transfer_to_agent("fibro_specialist", context) 
        if has_other:
            return await self._transfer_to_agent("other_specialist", context)
        else:
            return await self._transfer_to_agent("eligibility", context)