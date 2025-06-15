from datetime import datetime
import logging
from typing import Annotated
from pydantic import Field
from livekit.plugins import openai
from livekit.agents.llm import function_tool

from .base_agent import BaseAgent, RunContext, Agent
# from .common_functions import end_call

class Reservation(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                f"התאריך עכשיו הוא {datetime.now().strftime('%d.%m.%Y')}"
                "תפקידך הוא לשאול מתי יהיה נוח ללקוח שיחזרו אליו בשיחת טלפון."
                "אם הלקוח אומר שמתאים לו לדבר כעת העבירי אותו לסוכן הרפואי"
                "אל תגידי שאת מעבירה אותו לסוכן הרפואי פשוט תעבירי"
                " לאחר מכן ודאי את התאריך והשעה שקבעתם."
                "לאחר מכן סיים את השיחה"
            ),
            

            # tools=[update_name, update_phone, convert_datetime_to_speech, to_greeter, end_call],
            tools=[ ],
        )
        logger=logging.getLogger("restaurant-example")
        logger.info("Reservation agent initialized")    

    async def on_enter(self):
        # when the agent is added to the session, we'll initiate the conversation by
        # using the LLM to generate a reply
        self.session.generate_reply()


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
        
