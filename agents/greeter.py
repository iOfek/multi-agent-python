from datetime import datetime
import logging
from livekit.plugins import openai
from pydantic import Field
from livekit.agents.llm import function_tool

from agents.utils import load_prompt

from .base_agent import BaseAgent, RunContext, Agent

class Greeter(BaseAgent):
    def __init__(self, basic_agent_knowledge: str) -> None:
        super().__init__(
            instructions=load_prompt("greeter_prompt.yaml"),
        )
        logger = logging.getLogger("restaurant-example")
        self.basic_agent_knowledge = basic_agent_knowledge

    async def on_enter(self) -> None:
        await super().on_enter()
        # self.session.say("שלום, מדברת מערכת זינגר AI ממשרד עורכי הדין זינגר ושות'. אני מתקשרת אליך בעקבות הפנייה שהשארת לנו בנוגע למיצוי זכויות מול ביטוח לאומי. אפשר כמה דקות לדבר? ")

    @function_tool()
    async def to_reservation(self, context: RunContext) -> tuple[Agent, str]:
        """נקרא כאשר המשתמש רוצה לתאם פגישה במועד אחר.
 הפונקציה תאסוף את הפרטים הדרושים - תאריך ומעד הפגישה."""
        return await self._transfer_to_agent("reservation", context)

    @function_tool()
    async def to_medical(self, context: RunContext) -> tuple[Agent, str]:
        """נקרא כאשר המשתמש יכול לדבר כעת"""
        return await self._transfer_to_agent("medical", context) 