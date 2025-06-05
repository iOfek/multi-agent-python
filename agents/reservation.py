from typing import Annotated
from pydantic import Field
from livekit.plugins import openai
from livekit.agents.llm import function_tool

from .base_agent import BaseAgent, RunContext, Agent
from .common_functions import update_name, update_phone, to_greeter, end_call

class Reservation(BaseAgent):
    def __init__(self, basic_agent_knowledge: str) -> None:
        super().__init__(
            instructions=(
                "את מזכירה ידידותית AI במשרד עורכי הדין זינגר ושות'."
                "התאריך עכשיו הוא 06.06.2025"
                "תפקידך הוא לשאול מתי יהיה נוח ללקוח שיחזרו אליו בשיחת טלפון."
                "לאחר מכן ודאי את פרטי מועד השיחה שקבעתם."
                "לאחר מכן סיים את השיחה"
            ),
            tools=[update_name, update_phone, to_greeter, end_call],
        )
        self.basic_agent_knowledge = basic_agent_knowledge

    @function_tool()
    async def update_reservation_time(
        self,
        time: Annotated[str, Field(description="The phone call time")],
        context: RunContext,
    ) -> str:
        """נקרא כאשר המשתמש מספק את זמן השיחה הטלפונית.
        יש לאשר את הזמן עם המשתמש לפני קריאה לפונקציה."""
        userdata = context.userdata
        userdata.reservation_time = time
        return f"The phone call time is updated to {time}"

    @function_tool()
    async def confirm_reservation(self, context: RunContext) -> str | tuple[Agent, str]:
        """נקרא כאשר המשתמש מאשר את זמן השיחה הטלפונית.
        יש לאשר את הזמן עם המשתמש לפני קריאה לפונקציה."""
        userdata = context.userdata
        if not userdata.name or not userdata.customer_phone:
            return "אנא ספק את שמך ומספר הטלפון שלך תחילה."

        if not userdata.reservation_time:
            return "אנא ספק תחילה מועד נוח לשיחה הטלפונית. "

        return await self._transfer_to_agent("greeter", context) 