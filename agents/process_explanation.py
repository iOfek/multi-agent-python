from typing import Annotated, List, Optional
import logging
from pydantic import Field
from livekit.plugins import openai
from livekit.agents.llm import function_tool

from agents.utils import load_prompt

from .base_agent import BaseAgent, RunContext, Agent
from .common_functions import to_greeter

class ProcessExplanation(BaseAgent):
    def __init__(self, basic_agent_knowledge: str) -> None:
        super().__init__(
            instructions=load_prompt("process_explanation_prompt.yaml"),
            tools=[
                
            ],
        )
        logger = logging.getLogger("process-explanation-example")
        logger.info(f"Process explanation agent initialized with basic agent knowledge: {basic_agent_knowledge}")
        self.basic_agent_knowledge = basic_agent_knowledge

#     @function_tool()
#     async def explain_medical_file_building(
#         self,
#         context: RunContext,
#     ) -> str:
#         """נקרא כאשר יש להסביר את שלב בניית התיק הרפואי."""
#         return """שלב ראשון – בניית תיק רפואי:
# אנו נאסוף את המסמכים הרפואיים שלך, נבחן את מה שכבר יש בידך ונכוון אותך אם יש צורך להשלים מסמכים חסרים.
# עורך הדין עובר על כלל החומרים ובוחר את הרלוונטיים ביותר לתביעה."""

#     @function_tool()
#     async def explain_claims_submission(
#         self,
#         context: RunContext,
#     ) -> str:
#         """נקרא כאשר יש להסביר את שלב הגשת התביעות."""
#         return """שלב שני – הגשת התביעות:
# לאחר סידור החומרים, אנו מגישים את התביעות הרלוונטיות לביטוח לאומי בשמך."""

#     @function_tool()
#     async def explain_medical_committee(
#         self,
#         context: RunContext,
#     ) -> str:
#         """נקרא כאשר יש להסביר את שלב הוועדה הרפואית."""
#         return """שלב שלישי – ועדה רפואית:
# תוזמן לוועדה רפואית בביטוח לאומי – זו שיחה קצרה עם רופא שמתבססת בעיקר על המסמכים שהגשנו.
# נערוך איתך שיחת הכנה לפני כן. במידת הצורך, עורך הדין יוכל להגיע לוועדה יחד איתך."""

#     @function_tool()
#     async def explain_rehabilitation_meeting(
#         self,
#         context: RunContext,
#     ) -> str:
#         """נקרא כאשר יש להסביר את שלב פגישת השיקום המקצועי."""
#         return """שלב רביעי – פגישת שיקום מקצועי (אם רלוונטי):
# לאחר אישור התביעה, תוזמן לפגישה עם עובדת שיקום של ביטוח לאומי – שם תקבע תכנית שיקום ויינתן הסיוע הכספי."""

    @function_tool()
    async def confirm_understanding(
        self,
        understood: Annotated[bool, Field(description="האם הלקוח מציין שהוא הבין את כל התהליך שהוסבר")],
        context: RunContext,
    ) -> tuple[Agent, str]:
        """
        בסיום הסבר התהליך, הסוכן שואל אם הכל ברור.
        אם הלקוח הבין – מעביר לסוכן התיאומים לקביעת פגישה.
        אם לא – מאפשר לשאול שאלות הקשורות לארבעת שלבי התהליך בלבד.
        """
        logger = logging.getLogger("process-explanation")
        logger.info(f"Client confirmed understanding: {understood}")
        # context.userdata.process_explained = understood

        if understood:
            # סימון במערכת או חיווי אחר אפשרי לצורך העברה לסוכן אחר
            agent, _ = await self._transfer_to_agent("meeting_setup", context)
            return agent, "מעולה. נעבור כעת לתיאום פגישה עם עורך הדין."
        else:
            return self, "בשמחה אסביר שוב. האם יש חלק מסוים בתהליך שתרצה שאבהיר?"

