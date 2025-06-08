from typing import Annotated, List, Optional
import logging
from pydantic import Field
from livekit.plugins import openai
from livekit.agents.llm import function_tool

from agents.utils import load_prompt

from .base_agent import BaseAgent, RunContext, Agent
from .common_functions import to_greeter

class FibroSpecialist(BaseAgent):
    def __init__(self, basic_agent_knowledge: str) -> None:
        super().__init__(
            instructions=load_prompt("fibro_specialist_prompt.yaml"),
            tools=[
                
            ],
        )
        logger = logging.getLogger("fibro-specialist-example")
        logger.info(f"Fibro specialist agent initialized with basic agent knowledge: {basic_agent_knowledge}")
        self.basic_agent_knowledge = basic_agent_knowledge

    @function_tool()
    async def ask_diagnosis_date(
        self,
        diagnosis_date: Annotated[str, Field(description="The date when the condition started")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק את תאריך תחילת המחלה."""
        userdata = context.userdata
        userdata.diagnosis_date = diagnosis_date
        return f"תודה על המידע. תאריך תחילת המחלה נרשם."

    @function_tool()
    async def ask_severity_level(
        self,
        severity_level: Annotated[str, Field(description="The severity level of the condition")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק את דרגת החומרה של המחלה."""
        userdata = context.userdata
        userdata.severity_level = severity_level
        return f"תודה על המידע. דרגת החומרה נרשמה."

    @function_tool()
    async def ask_regular_treatment(
        self,
        regular_treatment: Annotated[str, Field(description="Whether the patient receives regular treatment")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק מידע על טיפול קבוע."""
        userdata = context.userdata
        userdata.regular_treatment = regular_treatment
        return f"תודה על המידע. המידע על טיפול קבוע נרשם."

    @function_tool()
    async def ask_previous_treatments(
        self,
        previous_treatments: Annotated[str, Field(description="Previous treatments tried")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק מידע על טיפולים קודמים."""
        userdata = context.userdata
        userdata.previous_treatments = previous_treatments
        return f"תודה על המידע. הטיפולים הקודמים נרשמו."

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
        has_other = userdata.has_other
        if has_other:
            return await self._transfer_to_agent("other_specialist", context)
        else:
            return await self._transfer_to_agent("eligibility", context)