from datetime import datetime
import logging
from typing import Annotated
from livekit.plugins import openai
from pydantic import Field
from livekit.agents.llm import function_tool

from agents.common_functions import convert_datetime_to_speech, end_call
from agents.utils import load_prompt

from .base_agent import BaseAgent, RunContext, Agent

class Greeter(BaseAgent):
    def __init__(self, basic_agent_knowledge: str) -> None:
        super().__init__(
            instructions=load_prompt("greeter_prompt.yaml"),
            tools=[ end_call],
            
        )
        logger = logging.getLogger("restaurant-example")
        logger.info(f"Reservation agent initialized with basic agent knowledge: {basic_agent_knowledge}")
        logger.info(f"התאריך עכשיו הוא {datetime.now().strftime('%d.%m.%Y')}")
        self.basic_agent_knowledge = basic_agent_knowledge


    async def on_enter(self) -> None:
        await super().on_enter()
        # self.session.say("שלום, מדברת מערכת זינגר AI ממשרד עורכי הדין זינגר ושות'. אני מתקשרת אליך בעקבות הפנייה שהשארת לנו בנוגע למיצוי זכויות מול ביטוח לאומי. אפשר כמה דקות לדבר? ")

#     @function_tool()
#     async def to_reservation(self, context: RunContext) -> tuple[Agent, str]:
#         """נקרא כאשר המשתמש לא פנוי לשוחח כעת.
#  הפונקציה תאסוף את הפרטים הדרושים - תאריך ומעד הפגישה."""
#         return await self._transfer_to_agent("reservation", context)

#     @function_tool()
#     async def to_eligibility(self, context: RunContext) -> tuple[Agent, str]:
#         """נקרא כאשר המשתמש יכול לדבר כעת"""
#         return await self._transfer_to_agent("eligibility", context) 

    @function_tool()
    async def listLawyerSlots(self, 
                              context: RunContext,
                              preference: Annotated[str, Field(description="The preference of the time of the day בוקר/צהריים/ערב")]) -> str:
        """הלקוח מציין מתי נוח לו לעשות את פגישת הייעוץ בבוקר, צהריים או ערב

        Args:
            preference: The preference of the time of the day בוקר/צהריים/ערב
        """

        if preference == "בוקר":
            return (
                convert_datetime_to_speech("26.06.2025:09:00") + ", " +
                convert_datetime_to_speech("26.06.2025:10:00") + ", " + 
                convert_datetime_to_speech("26.06.2025:11:00")
            )
        elif preference == "צהריים":
            return (
                convert_datetime_to_speech("26.06.2025:13:00") + ", " +
                convert_datetime_to_speech("26.06.2025:14:00") + ", " +
                convert_datetime_to_speech("26.06.2025:15:00")
            )
        elif preference == "ערב":
            return (
                convert_datetime_to_speech("26.06.2025:17:00") + ", " +
                convert_datetime_to_speech("26.06.2025:18:00") + ", " +
                convert_datetime_to_speech("26.06.2025:19:00")
            )
        else:
            return "לא הצלחתי להבין איזה זמן נוח לך"
        
    @function_tool()
    async def bookLawyerSlot(self, context: RunContext, time_slot: Annotated[str, Field(description="The time slot to book")]) -> str:
        """נקרא כאשר המשתמש מבקש לקבוע פגישה"""
        return "פגישה קובעה"
    