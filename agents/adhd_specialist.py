from typing import Annotated, List, Optional
import logging
from pydantic import Field
from livekit.plugins import openai
from livekit.agents.llm import function_tool
from livekit.agents.voice import Agent, RunContext

from agents.utils import load_prompt
from agents.base_agent import BaseAgent
from agents.common_functions import to_greeter

class AdhdSpecialist(BaseAgent):
    def __init__(self, basic_agent_knowledge: str) -> None:
        super().__init__(
            instructions=load_prompt("adhd_specialist_prompt.yaml"),
            tools=[
                
            ],
        )
        logger = logging.getLogger("adhd-specialist-example")
        logger.info(f"Adhd specialist agent initialized with basic agent knowledge: {basic_agent_knowledge}")
        self.basic_agent_knowledge = basic_agent_knowledge

    @function_tool()
    async def ask_first_diagnosis_date(
        self,
        first_diagnosis_date: Annotated[str, Field(description="The date of the first diagnosis")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק את תאריך האבחון הראשון שלו."""
        userdata = context.userdata
        userdata.first_diagnosis_date = first_diagnosis_date
        return f"תודה על המידע. תאריך האבחון הראשון נרשם."
    
    @function_tool()
    async def ask_medication_type(
        self,
        medication_type: Annotated[str, Field(description="The type of medication")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק את סוג התרופה שהוא נוטל."""
        userdata = context.userdata
        userdata.medication_type = medication_type
        return f"תודה על המידע. סוג התרופה נרשם."
    
    @function_tool()
    async def ask_medication_duration(
        self,
        medication_duration: Annotated[str, Field(description="The duration of the medication")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק את משך התרופה שהוא משתמש בה."""
        userdata = context.userdata
        userdata.medication_duration = medication_duration
        return f"תודה על המידע. משך התרופה נרשם."
    
    @function_tool()    
    async def ask_medication_changes(
        self,
        medication_changes: Annotated[str, Field(description="The changes in the medication")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק את השינויים בתרופה שהוא עשה במהלך השנים."""
        userdata = context.userdata
        userdata.medication_changes = medication_changes
        return f"תודה על המידע. השינויים בתרופה נרשמו."
    
    @function_tool()
    async def ask_side_effects(
        self,
        side_effects: Annotated[str, Field(description="The side effects of the medication")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק את התופעות הלוואי שהוא סובל מהתרופה."""
        userdata = context.userdata
        userdata.side_effects = side_effects
        return f"תודה על המידע. התופעות הלוואי נרשמו."
    

    @function_tool()
    async def to_specialist(
        self, 
        context: RunContext) -> tuple[Agent, str]:
        """נקרא כאשר המשתמש מעוניין להתעסק במומחה מיוחד."""
        userdata = context.userdata
        has_psychological = userdata.has_psychological
        has_migraine = userdata.has_migraine
        has_fibro = userdata.has_fibro
        has_other = userdata.has_other
        if has_psychological:
            return await self._transfer_to_agent("psyche_specialist", context)
        elif has_migraine:
            return await self._transfer_to_agent("migraine_specialist", context)
        elif has_fibro:
            return await self._transfer_to_agent("fibro_specialist", context) 
        elif has_other:
            return await self._transfer_to_agent("other_specialist", context)
        else:
            return await self._transfer_to_agent("eligibility", context)
    