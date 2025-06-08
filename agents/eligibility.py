from datetime import datetime
import logging
from typing import Annotated
from livekit.plugins import openai
from pydantic import Field
from livekit.agents.llm import function_tool

from agents.utils import load_prompt

from .base_agent import BaseAgent, RunContext, Agent

class Eligibility(BaseAgent):
    def __init__(self, basic_agent_knowledge: str) -> None:
        super().__init__(
            instructions=load_prompt("eligibility.yaml"),
            tools=[
            ],
        )
        logger = logging.getLogger("restaurant-example")
        logger.info(f"Reservation agent initialized with basic agent knowledge: {basic_agent_knowledge}")
        logger.info(f"התאריך עכשיו הוא {datetime.now().strftime('%d.%m.%Y')}")
        self.basic_agent_knowledge = basic_agent_knowledge

    @function_tool()
    async def check_income_threshold(
        self,
        monthly_income: Annotated[float, Field(description="ההכנסה החודשית ברוטו של הלקוח")],
        context: RunContext,
    ) -> str:
        """בודק אם ההכנסה החודשית של הלקוח נמוכה מ-8,000 ש"ח."""
        context.userdata.monthly_income = monthly_income
        logger = logging.getLogger("eligibility-check")
        logger.info(f"Monthly income set to {monthly_income} ₪")

        if monthly_income < 8000:
            return "✔️ ההכנסה נמוכה מ-8,000 ש״ח – עומד בתנאי הסף."
        else:
            return "⚠️ ההכנסה גבוהה מ-8,000 ש״ח – רק מקרים רפואיים חמורים עשויים לזכות."


    @function_tool()
    async def check_employment_duration(
        self,
        employment_duration_months: Annotated[int, Field(description="מספר חודשי העבודה ברצף באותו מקום עבודה")],
        context: RunContext,
    ) -> str:
        """בודק אם הלקוח עבד ברציפות באותו מקום במשך שנה לפחות."""
        context.userdata.employment_duration_months = employment_duration_months
        logger = logging.getLogger("eligibility-check")
        logger.info(f"Employment duration: {employment_duration_months} months")

        if employment_duration_months >= 12:
            return "✔️ עבד שנה לפחות – תנאי סף מתקיים."
        else:
            return "⚠️ פחות משנה – ייתכן שהדבר ישפיע על הסיכוי לתביעה."


    @function_tool()
    async def check_earning_impact(
        self,
        earning_impact: Annotated[bool, Field(description="האם היכולת להשתכר נפגעה בעקבות הבעיה הרפואית")],
        context: RunContext,
    ) -> str:
        """בודק האם הלקוח איבד עבודה או ירד ביכולת ההשתכרות בעקבות בעיה רפואית."""
        context.userdata.earning_impact = earning_impact
        logger = logging.getLogger("eligibility-check")
        logger.info(f"Earning impact: {earning_impact}")

        if earning_impact:
            return "✔️ קיימת ירידה בהכנסה בעקבות המצב – יש פוטנציאל לתביעת נכות כללית או שיקום מקצועי."
        else:
            return "ℹ️ אין ירידה ביכולת ההשתכרות – ייתכן שזה יחליש את התיק."


    @function_tool()
    async def check_medical_documentation(
        self,
        has_medical_documents: Annotated[bool, Field(description="האם יש אבחנות רפואיות, מסמכים או תיעוד טיפולים")],
        context: RunContext,
    ) -> str:
        """בודק אם ללקוח יש תיעוד רפואי מספק."""
        context.userdata.has_medical_documents = has_medical_documents
        logger = logging.getLogger("eligibility-check")
        logger.info(f"Has medical documents: {has_medical_documents}")

        if has_medical_documents:
            return "✔️ קיים תיעוד רפואי – מצוין."
        else:
            return "⚠️ אין תיעוד רפואי – יש להפנות להשלמת מסמכים בהמשך."


    @function_tool()
    async def check_educational_impact(
        self,
        education_affected: Annotated[bool, Field(description="האם הלימודים הושפעו מהמצב הרפואי או הופסקו")],
        context: RunContext,
    ) -> str:
        """בודק אם הלימודים הושפעו מהמצב הרפואי – רלוונטי לסטודנטים."""
        context.userdata.education_affected = education_affected
        logger = logging.getLogger("eligibility-check")
        logger.info(f"Education affected: {education_affected}")

        if education_affected:
            return "✔️ הלימודים הושפעו מהמצב – יש אפשרות לתמיכה או סיוע."
        else:
            return "ℹ️ הלימודים לא הושפעו – המידע נרשם."
    
    @function_tool()
    async def to_process_explanation(
        self,
        context: RunContext,
    ) -> str:
        """מסביר את התהליך של העבודה עם משרד עו"ד זינגר ושות'."""
        
        return await self._transfer_to_agent("process_explanation", context)

    
   