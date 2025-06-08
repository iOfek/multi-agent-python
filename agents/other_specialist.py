from typing import Annotated, List, Optional
import logging
from pydantic import Field
from livekit.plugins import openai
from livekit.agents.llm import function_tool

from agents.utils import load_prompt

from .base_agent import BaseAgent, RunContext, Agent
from .common_functions import to_greeter

class OtherSpecialist(BaseAgent):
    def __init__(self, basic_agent_knowledge: str) -> None:
        super().__init__(
            instructions=load_prompt("other_specialist_prompt.yaml"),
            tools=[
                
            ],
        )
        logger = logging.getLogger("other-specialist-example")
        logger.info(f"Other specialist agent initialized with basic agent knowledge: {basic_agent_knowledge}")
        self.basic_agent_knowledge = basic_agent_knowledge

    @function_tool()
    async def ask_duration(
        self,
        duration: Annotated[str, Field(description="The duration of the condition")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק את תאריך תחילת המחלה."""
        userdata = context.userdata
        userdata.duration = duration
        return f"תודה על המידע. תאריך תחילת המחלה נרשם."

    @function_tool()
    async def ask_medication_type(
        self,
        medication_type: Annotated[str, Field(description="The type of medication the patient is taking")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק את דרגת החומרה של המחלה."""
        userdata = context.userdata
        userdata.medication_type = medication_type
        return f"תודה על המידע. דרגת החומרה נרשמה."

    @function_tool()
    async def ask_medication_duration(
        self,
        medication_duration: Annotated[str, Field(description="The duration of the medication")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק מידע על טיפול קבוע."""
        userdata = context.userdata
        userdata.medication_duration = medication_duration
        return f"תודה על המידע. המידע על טיפול קבוע נרשם."

    @function_tool()
    async def ask_medical_diagnosis(
        self,
        medical_diagnosis: Annotated[str, Field(description="Whether the patient has a medical diagnosis")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק מידע על טיפולים קודמים."""
        userdata = context.userdata
        userdata.medical_diagnosis = medical_diagnosis
        return f"תודה על המידע. הטיפולים הקודמים נרשמו."

    @function_tool()
    async def to_eligibility(
        self, 
        context: RunContext) -> tuple[Agent, str]:
        """נקרא לאחר שהלקוח ענה על כל השאלות."""
        return await self._transfer_to_agent("eligibility", context)