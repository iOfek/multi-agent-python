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
            # llm=openai.LLM.with_azure(
            #     azure_deployment="gpt-4.1",
            #     azure_endpoint=r"https://iofek-mbcpsptu-eastus2.cognitiveservices.azure.com/openai/deployments/gpt-4.1/chat/completions?api-version=2025-01-01-preview",
            #     api_key="4P3LarHA127RY4jDSABYaG5MA6QV4XrBpsJfK1LkjFOEsqcsTsz9JQQJ99BEACHYHv6XJ3w3AAAAACOGME7w",
            #     api_version="2025-01-01-preview",
            #     parallel_tool_calls=False,
            # ),
        )
        logger = logging.getLogger("restaurant-example")
        logger.info(f"Reservation agent initialized with basic agent knowledge: {basic_agent_knowledge}")
        logger.info(f"התאריך עכשיו הוא {datetime.now().strftime('%d.%m.%Y')}")
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