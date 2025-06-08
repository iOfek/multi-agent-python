from typing import Annotated, List, Optional
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
                "תפקידך הוא לשאול כמה שאלות כדי להבין אם אנחנו יכולים לעזור ללקוח, ובמידה וכן נקבע ללקול פגישה עם עורך הדין גל זינגר."
                "\n\nתשאל את השאלות הבאות אחת אחר השנייה לפי הסדר הבא:"
                "\n- האם אתה סטודנט או לומד כרגע בלימודי תעודה?"
                "\n- אם כן, מה אתה לומד ובאיזו שנה אתה נמצא?"
                "\n- איך קוראים לך?"
                "\n- בן/בת כמה אתה?"
                "\n- האם אתה עובד כיום? כמה זמן אתה בעבודה הנוכחית?"
                "\n- במהלך השנה האחרונה, האם הכנסתך החודשית הייתה מתחת ל-7,500 ש'ח בממוצע?"
                "\n- מה גובה ההכנסה החודשית שלך בברוטו?"
                "\n- תארי לי בבקשה את המגבלות הרפואיות שלך בקצרה."
                "\n- האם את לוקחת כדורים?"
                "\n- האם את נפגשת באופן קבוע עם רופאים? תארי לי איזה בבקשה."
                "\n- האם הבעיות שתיארת מאובחנות או שאת סובלת מהן אך לא פנית לגורמים רפואיים?"
                "\n\nאם הלקוח מתאר הפרעת קשב וריכוז (ADHD):"
                "\n- ממתי האבחון הראשון שלך?"
                "\n- האם את נוטלת טיפול תרופתי יומיומי? איזה?"
                "\n- כמה זמן את משתמשת בתרופה?"
                "\n- האם החלפת תרופות במהלך השנים? אילו?"
                "\n- האם את סובלת מתופעות לוואי? תוכלי לתאר אותן?"
                "\n\nאם מתואר מצב פסיכיאטרי (חרדה, דיכאון, PTSD, OCD):"
                "\n- כמה זמן את סובלת מהבעיה?"
                "\n- האם את מטופלת על ידי פסיכיאטר? כמה זמן?"
                "\n- האם יש לך אבחנה רשמית?"
                "\n- האם את נוטלת תרופות? אילו וכמה זמן?"
                "\n\nאם מדובר במיגרנות:"
                "\n- כמה התקפים יש לך בחודש?"
                "\n- האם ניסית טיפולים תרופתיים? אילו?"
                "\n- האם יש תיעוד רפואי למצב?"
                "\n\nאם מדובר בקרוהן/קוליטיס/פיברומיאלגיה:"
                "\n- מתי התחילה המחלה?"
                "\n- מה דרגת החומרה?"
                "\n- האם את מטופלת באופן קבוע?"
                "\n- אילו טיפולים ניסית עד כה?"
                "\n\nבמידה ומדובר בהפרעה שלא מופיעה כאן יש לכתוב אותה ולשאול את השאלות הבאות:"
                "\n- כמה זמן את סובלת מההפרעה הזאת?"
                "\n- האם את מטופלת בכדורים בגינה?"
                "\n- האם יש אבחון שלה?"
            ),
            tools=[to_greeter],
        )

    @function_tool()
    async def update_student_status(
        self,
        context: RunContext,
        is_student: Annotated[bool, Field(description="Whether the user is currently a student or in a certification program")],
        study_details: Annotated[Optional[str], Field(description="If is_student is True, what they are studying and in which year")] = None,
    ) -> str:
        """Called when the user provides information about their student status."""
        userdata = context.userdata
        userdata.is_student = is_student
        userdata.study_details = study_details
        
        if is_student and study_details:
            return f"תודה על המידע. אני רואה שאתה סטודנט/לומד {study_details}."
        elif is_student:
            return "תודה על המידע. אשמח לדעת מה אתה לומד ובאיזו שנה אתה נמצא."
        else:
            return "תודה על המידע. אני מבינה שאתה לא סטודנט או לומד כרגע."

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