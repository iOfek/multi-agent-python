from livekit.plugins import openai
from pydantic import Field
from livekit.agents.llm import function_tool

from .base_agent import BaseAgent, RunContext, Agent

class Greeter(BaseAgent):
    def __init__(self, basic_agent_knowledge: str) -> None:
        super().__init__(
            instructions=(
                "את מזכירה ידידותית AI במשרד עורכי הדין זינגר ושות'."
                "המידע הבסיסי שלך הוא: {basic_agent_knowledge}"
                "את מתקשרת בעקבות פניה שהלקוח השאיר לכם בנוגע למיצוי זכויות מול ביטוח לאומי."
                "תפקידך הוא לברך את המתקשר ולהבין אם הוא יכול לדבר עכשיו כמה דקות"
                "או שתנסי לתאם מולו פגישה במועד אחר."
                "תעבירי אותו לסוכן אחר באמצעות פונקציות כלים."
            ),
            llm=openai.LLM.with_azure(
                azure_deployment="gpt-4.1",
                azure_endpoint=r"https://iofek-mbcpsptu-eastus2.cognitiveservices.azure.com/openai/deployments/gpt-4.1/chat/completions?api-version=2025-01-01-preview",
                api_key="4P3LarHA127RY4jDSABYaG5MA6QV4XrBpsJfK1LkjFOEsqcsTsz9JQQJ99BEACHYHv6XJ3w3AAAAACOGME7w",
                api_version="2025-01-01-preview",
                parallel_tool_calls=False,
            ),
        )
        self.basic_agent_knowledge = basic_agent_knowledge

    async def on_enter(self) -> None:
        await super().on_enter()
        # self.session.say("שלום, מדברת מערכת זינגר AI ממשרד עורכי הדין זינגר ושות'. אני מתקשרת אליך בעקבות הפנייה שהשארת לנו בנוגע למיצוי זכויות מול ביטוח לאומי. אפשר כמה דקות לדבר? ")

    @function_tool()
    async def to_reservation(self, context: RunContext) -> tuple[Agent, str]:
        """נקרא כאשר המשתמש רוצה לתאם פגישה במועד אחר.
הפונקציה הזו מטפלת במעבר לסוכן התיאומים,
אשר יאסוף את הפרטים הדרושים - תאריך ומעד הפגישה."""
        return await self._transfer_to_agent("reservation", context)

    @function_tool()
    async def to_takeaway(self, context: RunContext) -> tuple[Agent, str]:
        """Called when the user wants to place a takeaway order.
        This includes handling orders for pickup, delivery, or when the user wants to
        proceed to checkout with their existing order."""
        return await self._transfer_to_agent("takeaway", context) 