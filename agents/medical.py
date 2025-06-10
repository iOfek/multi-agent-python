from typing import Annotated, List, Optional
import logging
from pydantic import Field
from livekit.plugins import openai
from livekit.agents.llm import function_tool

from agents.utils import load_prompt

from .base_agent import BaseAgent, RunContext, Agent
from .common_functions import to_greeter

class Medical(BaseAgent):
    def __init__(self, basic_agent_knowledge: str) -> None:
        super().__init__(
            instructions=load_prompt("medical_prompt.yaml") + "\n\n" +  "basic_agent_knowledge",
            tools=[
                # to_greeter,
            ],
        )
        logger = logging.getLogger("medical-example")
        
        logger.info(f"Medical agent initialized with basic agent knowledge: {basic_agent_knowledge}")
        self.basic_agent_knowledge = basic_agent_knowledge

    @function_tool()
    async def ask_medical_limitations(
        self,
        limitations: Annotated[str, Field(description="The client's medical limitations")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מתאר את המגבלות הרפואיות שלו."""
        userdata = context.userdata
        userdata.medical_limitations = limitations
        logger = logging.getLogger("medical-example")
        logger.info(f"Medical limitations updated: {limitations}")
        return f"תודה על המידע. המגבלות הרפואיות שלך נרשמו."

    @function_tool()
    async def ask_medications(
        self,
        medications: Annotated[str, Field(description="The client's current medications")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מתאר את התרופות שהוא נוטל."""
        userdata = context.userdata
        userdata.medications = medications
        logger = logging.getLogger("medical-example")
        logger.info(f"Medications updated: {medications}")
        return f"תודה על המידע. התרופות שלך נרשמו."

    @function_tool()
    async def ask_doctor_visits(
        self,
        doctors: Annotated[str, Field(description="The client's regular doctors")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מתאר את הרופאים שהוא פוגש באופן קבוע."""
        userdata = context.userdata
        userdata.regular_doctors = doctors
        logger = logging.getLogger("medical-example")
        logger.info(f"Regular doctors updated: {doctors}")
        return f"תודה על המידע. הרופאים שלך נרשמו."

    @function_tool()
    async def ask_diagnosis_status(
        self,
        diagnosis: Annotated[str, Field(description="Whether the problems are diagnosed")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מתאר את סטטוס האבחון של הבעיות."""
        userdata = context.userdata
        userdata.diagnosis_status = diagnosis
        logger = logging.getLogger("medical-example")
        logger.info(f"Diagnosis status updated: {diagnosis}")
        return f"תודה על המידע. סטטוס האבחון נרשם."
    
    @function_tool()
    async def to_specialist(
        self, 
        has_adhd: Annotated[bool, Field(description="whether the client has adhd")],
        has_migraine: Annotated[bool, Field(description="whether the client has migraines")],
        has_fibro: Annotated[bool, Field(description="whether the client has auto-immune diseases")],
        has_psychological: Annotated[bool, Field(description="whether the client has psychological problems")],
        has_other: Annotated[bool, Field(description="whether the client has other medical issues that are not adhd, migraine, auto-immune diseases, psychological / psycheciatric related")],
        context: RunContext) -> tuple[Agent, str]:
        """נקרא כאשר המשתמש מעוניין להתעסק במומחה מיוחד."""
        userdata = context.userdata
        userdata.has_adhd = has_adhd
        userdata.has_migraine = has_migraine
        userdata.has_fibro = has_fibro
        userdata.has_psychological = has_psychological
        userdata.has_other = has_other
        if has_adhd:
            return await self._transfer_to_agent("adhd_specialist", context)
        elif has_migraine:
            return await self._transfer_to_agent("migraine_specialist", context)
        elif has_fibro:
            return await self._transfer_to_agent("fibro_specialist", context)
        elif has_psychological:
            return await self._transfer_to_agent("psyche_specialist", context)
        elif has_other:
            return await self._transfer_to_agent("other_specialist", context)
        else:
            return await self._transfer_to_agent("eligibility", context)
    
    @function_tool()
    async def update_medical_info(self,
        limitations: Annotated[str, Field(description="The client's medical limitations")],
        medications: Annotated[str, Field(description="The client's current medications")],
        doctors: Annotated[str, Field(description="The client's regular doctors")],
        diagnosis: Annotated[str, Field(description="Whether the problems are diagnosed")],
        context: RunContext,
    ) -> tuple[Agent, str]:
        """נקרא כאשר המשתמש מעוניין לעדכן את המידע הרפואי שלו."""
        userdata = context.userdata
        userdata.medical_limitations += " "+limitations
        userdata.medications += " "+medications
        userdata.regular_doctors += " "+doctors
        userdata.diagnosis_status += " "+diagnosis
    


