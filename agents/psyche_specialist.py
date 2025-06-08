from typing import Annotated, List, Optional
import logging
from pydantic import Field
from livekit.plugins import openai
from livekit.agents.llm import function_tool

from agents.utils import load_prompt

from .base_agent import BaseAgent, RunContext, Agent
from .common_functions import to_greeter

class PsycheSpecialist(BaseAgent):
    def __init__(self, basic_agent_knowledge: str) -> None:
        super().__init__(
            instructions=load_prompt("psyche_specialist_prompt.yaml"),
            tools=[
                
            ],
        )
        logger = logging.getLogger("psyche-specialist-example")
        logger.info(f"Psyche specialist agent initialized with basic agent knowledge: {basic_agent_knowledge}")
        self.basic_agent_knowledge = basic_agent_knowledge

    @function_tool()
    async def ask_duration(
        self,
        duration: Annotated[str, Field(description="Duration of the condition")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק את משך הבעיה."""
        userdata = context.userdata
        userdata.duration = duration
        return f"תודה על המידע. משך הבעיה נרשם."

    @function_tool()
    async def ask_psychologist_treatment(
        self,
        psychologist_treatment: Annotated[str, Field(description="Whether treated by a psychiatrist")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק מידע על טיפול פסיכיאטרי."""
        userdata = context.userdata
        userdata.psychologist_treatment = psychologist_treatment
        return f"תודה על המידע. המידע על טיפול פסיכיאטרי נרשם."

    @function_tool()
    async def ask_psychologist_treatment_duration(
        self,
        treatment_duration: Annotated[str, Field(description="Duration of psychiatric treatment")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק את משך הטיפול הפסיכיאטרי."""
        userdata = context.userdata
        userdata.treatment_duration = treatment_duration
        return f"תודה על המידע. משך הטיפול הפסיכיאטרי נרשם."

    @function_tool()
    async def ask_medical_diagnosis(
        self,
        medical_diagnosis: Annotated[str, Field(description="Official medical diagnosis")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק מידע על אבחנה רשמית."""
        userdata = context.userdata
        userdata.medical_diagnosis = medical_diagnosis
        return f"תודה על המידע. האבחנה הרשמית נרשמה."

    @function_tool()
    async def ask_medication_type(
        self,
        medication_type: Annotated[str, Field(description="Types of medications taken")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק מידע על תרופות."""
        userdata = context.userdata
        userdata.medication_type = medication_type
        return f"תודה על המידע. המידע על התרופות נרשם."

    @function_tool()
    async def ask_medication_duration(
        self,
        medication_duration: Annotated[str, Field(description="Duration of medication use")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק את משך השימוש בתרופה."""
        userdata = context.userdata
        userdata.medication_duration = medication_duration
        return f"תודה על המידע. משך השימוש בתרופה נרשם."

    @function_tool()
    async def to_specialist(
        self, 
        context: RunContext) -> tuple[Agent, str]:
        """נקרא כאשר המשתמש מעוניין להתעסק במומחה מיוחד."""
        userdata = context.userdata
        has_migraine = userdata.has_migraine
        has_fibro = userdata.has_fibro
        has_other = userdata.has_other
        if has_migraine:
            return await self._transfer_to_agent("migraine_specialist", context)
        elif has_fibro:
            return await self._transfer_to_agent("fibro_specialist", context) 
        elif has_other:
            return await self._transfer_to_agent("other_specialist", context)
        else:
            return await self._transfer_to_agent("eligibility", context)