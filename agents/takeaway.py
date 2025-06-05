from typing import Annotated, List
from pydantic import Field
from livekit.plugins import openai
from livekit.agents.llm import function_tool

from .base_agent import BaseAgent, RunContext, Agent
from .common_functions import to_greeter

class Takeaway(BaseAgent):
    def __init__(self, basic_agent_knowledge: str) -> None:
        super().__init__(
            instructions=(
                "את מזכירה ידידותית AI במשרד עורכי הדין זינגר ושות'."
                "תפקידך הוא לקבל הזמנה מהלקוח ולאשר את ההזמנה עם הלקוח."
                "אם יש צורך להסביר מחירון של מוצרים שונים, תפקידך הוא להסביר את המחירון ולבקש מהלקוח לבחור את המוצרים שהוא רוצה."
            ),
            tools=[to_greeter],
        )

    @function_tool()
    async def update_order(
        self,
        items: Annotated[List[str], Field(description="The items of the full order")],
        context: RunContext,
    ) -> str:
        """Called when the user create or update their order."""
        userdata = context.userdata
        userdata.order = items
        return f"The order is updated to {items}"

    @function_tool()
    async def to_checkout(self, context: RunContext) -> str | tuple[Agent, str]:
        """Called when the user confirms the order."""
        userdata = context.userdata
        if not userdata.order:
            return "No takeaway order found. Please make an order first."

        return await self._transfer_to_agent("checkout", context) 