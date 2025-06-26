import asyncio
from datetime import datetime
import json
import logging
import os
import tempfile
import aiohttp
from dotenv import load_dotenv

from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.llm import function_tool
from livekit.agents.voice import AgentSession, Agent, RunContext
from livekit.agents.voice.room_io import RoomInputOptions
from livekit.plugins import openai, silero, google, noise_cancellation
from livekit import api
from openai.types.beta.realtime.session import TurnDetection

from agents import (
    UserData,
    Greeter,
    Reservation,
    Takeaway,
    Checkout,
)
from agents.adhd_specialist import AdhdSpecialist
from agents.common_functions import end_call, convert_datetime_to_speech
from agents.eligibility import Eligibility
from agents.fibro_specialist import FibroSpecialist
from agents.medical import Medical
from agents.meeting_setup import MeetingSetup
from agents.migraine_specialist import MigraineSpecialist
from agents.process_explanation import ProcessExplanation
from agents.psyche_specialist import PsycheSpecialist
from agents.other_specialist import OtherSpecialist
from agents.specialist import Specialist
from agents.utils import load_prompt

from twilio.rest import Client

from calendar_service import CalendarService

# ---------------------------------------------------------------------------
# ENV & GLOBALS
# ---------------------------------------------------------------------------
logger = logging.getLogger("restaurant-example")
logger.setLevel(logging.INFO)

load_dotenv()

# ---------------------------------------------------------------------------
# TWILIO CLIENT
# ---------------------------------------------------------------------------
client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

# ---------------------------------------------------------------------------
# SUPERVISOR AGENT – heavy‑lifting LLM + tools
# ---------------------------------------------------------------------------

class SupervisorAgent(Agent):
    """High‑capacity agent that handles complex queries and tool usage."""

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                """
                You are the supervisor. Provide detailed, accurate answers.
                Use tools when they are available. Never refuse without a reason.
                """
            ),
            tools=[],
            llm=openai.LLM.with_azure(
                azure_deployment=os.getenv("AZURE_OPENAI_GPT41_DEPLOYMENT"),
                azure_endpoint=os.getenv("AZURE_OPENAI_GPT41_ENDPOINT"),
                api_key=os.getenv("AZURE_OPENAI_NORTHCENTRALUS_API_KEY"),
                api_version="2025-01-01-preview",
            ),
        )

    # Example tool ----------------------------------------------------------
    @function_tool()
    async def lookup_weather(
        self, context: RunContext, location: str
    ) -> dict[str, str | int]:
        """Return mocked weather data for *location*. Replace with real API."""
        return {"location": location, "description": "Sunny", "temperature_c": 25}

# ---------------------------------------------------------------------------
# CHAT AGENT – realtime, low‑latency front‑end
# ---------------------------------------------------------------------------

class ChatAgent(Agent):
    """Realtime agent that greets the user and hands off when needed."""

    def __init__(self, supervisor) -> None:
        self.supervisor = supervisor
        super().__init__(
            instructions=(
                """
                ## Identity
                You are a friendly, fast voice assistant calling from זינגר ושות, משרד עורכי-הדין זינגר ושות.
                
                ## Demeanor
                אמפתי, ענייני ומקצועי, עם קשב רב לצורכי המתקשר.

                ## Tone
                חם, מנומס ובהיר, בעברית רהוטה.

                ## Level of Enthusiasm
                בינוני-גבוה – ניכר רצון אמיתי לעזור אך ללא לחץ.

                ## Level of Formality
                פורמלי-ידידותי (לדוגמה: "שלום" / "תודה על זמנך").

                ## Level of Emotion
                מביעה אמפתיה ושיתוף-פעולה, אך נשארת מאוזנת.

                ## Filler Words
                הרבה ("אממ", "אה…" רק אם דרוש לרצף דיבור טבעי).  

                ## Pacing
                מהיר; חוזרת על מידע חשוב.

                ## Function Tools
                - endConversation()                  → סיום השיחה.
                - to_eligibility()                  → מעביר לסוכן של תיאום פגישה.

                ## Other details
                - Avoid technical jargon; use plain language so that instructions are easy to understand.
                - אם הלקוח מתקן פרט – הוד(י) על התיקון ואשר/י אותו.  

                
                ## Instructions
                - "פתחי: \"שלום, אני מתקשרת בקשר לפנייה שלך למימון לימודים, האם אפשר לדבר?\""
                - "אם שואל \"על מה מדובר?\": \"השארת פרטים על מימון לימודים של עד 65,000 ש\"ח בעקבות מגבלות רפואיות, כנראה בפייסבוק או באינסטגרם. האם זה זמן נוח לדבר?\""
                - אם הלקוח משיב 'לא' אז תקרא ל endConversation()
                - אם הלקוח משיב 'כן' אז תקרא ל to_eligibility()
                """
            ),
             tools=[],
            llm=openai.realtime.RealtimeModel.with_azure(
                azure_deployment=os.getenv("AZURE_OPENAI_GPT4O_REALTIME_DEPLOYMENT"),
                azure_endpoint=os.getenv("AZURE_OPENAI_GPT4O_REALTIME_ENDPOINT"),
                api_key=os.getenv("AZURE_OPENAI_SWEDENCENTRAL_API_KEY"),
                api_version="2024-10-01-preview",
                #  turn_detection=TurnDetection(
                #     type="server_vad",
                #     threshold=0.8,
                #     prefix_padding_ms=300,
                #     silence_duration_ms=500,
                #     create_response=True,
                #     interrupt_response=False,
                # )
                # voice="coral"
            ),

            # llm=openai.LLM.with_azure(
            #     azure_deployment=os.getenv("AZURE_OPENAI_GPT41_DEPLOYMENT"),
            #     azure_endpoint=os.getenv("AZURE_OPENAI_GPT41_ENDPOINT"),
            #     api_key=os.getenv("AZURE_OPENAI_NORTHCENTRALUS_API_KEY"),
            #     api_version="2025-01-01-preview",
            # ),
        )

    # Tool that triggers LiveKit's automatic handoff -----------------------
    @function_tool()
    async def endConversation(self, context: RunContext):
        """
        סיום השיחה.
        """
        await end_call(context)

    @function_tool()
    async def to_eligibility(self):
        """
        מעביר לסוכן של תיאום פגישה.
        """
        return EligibilityAgent(self.supervisor), "בסדר גמור. מיד נתחיל"

# ---------------------------------------------------------------------------
# Eligibility Agent – realtime, low‑latency front‑end
# ---------------------------------------------------------------------------

class EligibilityAgent(Agent):
    """Realtime agent that greets the user and hands off when needed."""

    def __init__(self, supervisor) -> None:
        self.supervisor = supervisor
        super().__init__(
            instructions=(
                """
                ## Task
                ליזום או לקבל שיחות ממועמדים שהשאירו פרטים לגבי מימון לימודים (עד 65,000 ₪) עקב מגבלות רפואיות; לבדוק זכאות ע״פ שאלון, ואז או לקבוע פגישה, או להסביר שאינם זכאים ולהציע שירותים משפטיים אחרים.

                ## Demeanor
                אמפתי, ענייני ומקצועי, עם קשב רב לצורכי המתקשר.

                ## Tone
                חם, מנומס ובהיר, בעברית רהוטה.

                ## Level of Enthusiasm
                בינוני-גבוה – ניכר רצון אמיתי לעזור אך ללא לחץ.

                ## Level of Formality
                פורמלי-ידידותי (לדוגמה: "שלום" / "תודה על זמנך").

                ## Level of Emotion
                מביעה אמפתיה ושיתוף-פעולה, אך נשארת מאוזנת.

                ## Filler Words
                הרבה ("אממ", "אה…" רק אם דרוש לרצף דיבור טבעי).  

                ## Pacing
                מהיר; חוזרת על מידע חשוב.

                ## Function Tools
                - listLawyerSlots(preference)       → מחזיר רשימת מועדי פגישה זמינים.
                - getStoredUserData()               → מחזיר אובייקט עם נתוני המשתמש הידועים (אולי ריקים).
                - updateCRM(value)      → שומר/מעדכן שדה ב-CRM.
                - checkEligibility(userData)        → מחזיר { eligible: bool, reason: string }.
                - bookLawyerSlot(slotId)            → קובע פגישה ומחזיר אישור.
                - sendConfirmation(channel, text)   → שולח SMS/WhatsApp/Email.
                - to_reservation()                  → מעביר לסוכן של תיאום פגישה.

                ## Other details
                - Never allow the user to interrupt mid sentence.
                - If the user speaks while you are speaking, ignore the user's input and continue your sentence.
                - Keep responses short and segmented—ideally one to two concise sentences per step.
                - Avoid technical jargon; use plain language so that instructions are easy to understand.
                - אם הלקוח מתקן פרט – הוד(י) על התיקון ואשר/י אותו.  
                - אם הלקוח מבקש נציג אנושי, או שלא הובַן 3 פעמים, קריאה: escalateToHuman(reason) וסיום אדיב.

                
                
                ## Instructions
                - יש לעקוב אחר Conversation States במדויק.
                - כל שינוי או תיקון שחוזר הלקוח – אשר-י במפורש.

                ## Conversation States
                
                - id: 3_introduce_self
                    description: הצגת הזהות ומטרת השאלון.
                    instructions:
                    - "קודם אציג את עצמי, מדברת מערכת זינגר AI ממשרד עורכי-הדין זינגר ושות'. אשאל אותך כמה שאלות כדי להבין אם נוכל לעזור לך, ובמידה וכן – נקבע פגישה עם עורך הדין גל זינגר."
                    examples:
                    - "אשאל כמה פרטים קצרים לגבי מצבך, בסדר?"
                    transitions:
                    - next_step: 4_income_question
                        condition: לאחר ההצגה

                - id: 4_income_question
                    description: בדיקת תנאי הכנסה.
                    instructions:
                    - "שאלה: \"האם אתה מרוויח פחות מ-8,000(שמונת אלפים) שקלים ברוטו בחודש?\""
                    - "אם הלקוח משיב 'לא' אז תקרא ל to_not_eligible()"
                    examples:
                    - "הכנסתך החודשית ברוטו נמוכה מ-8,000 ₪?"
                    transitions:
                    - next_step: 6_medical_overview
                        condition: הלקוח משיב 'כן'
                        
                - id: 6_medical_overview
                    description: איסוף מידע על מגבלות רפואיות.
                    instructions:
                    - "בקש/י: \"אשמח אם תוכל לתאר בקצרה את המגבלות הרפואיות שלך.\""
                    - "תן/י דוגמאות: ADHD, חרדה, דיכאון, מיגרנה, מחלות אוטואימוניות (פיברומיאלגיה, קרוהן, קוליטיס) וכו'."
                    examples:
                    - "לדוגמה, האם אתה סובל ממיגרנה כרונית או מבעיה אחרת?"
                    transitions:
                    - next_step: 7_only_ADHD_check
                        condition: רק ADHD ולא הוזכרו בעיות אחרות
                    - next_step: 8_confirm_qualification
                        condition: הוזכרו בעיות נוספות או אחרות

                - id: 7_only_ADHD_check
                    description: סינון כאשר מדובר רק ב-ADHD.
                    instructions:
                    - "שאלי: \"האם יש לך אבחון רשמי ל-ADHD?\""
                    - "שאלי: \"האם אתה מקבל טיפול תרופתי?\""
                    - "שאלי: \"האם אתה סטודנט או לומד מעל 12 שעות שבועיות במסגרת כלשהי?\""
                    - "אם אחד משני התנאים (אבחון+טיפול, לימודים 12 ש\"ש) לא מתקיימים → updateCRM(\"לא עומד בתנאי ADHD\") והמשך ל-5_not_eligible"
                    examples:
                    - "האם אתה לומד לפחות 12 שעות בשבוע?"
                    transitions:
                    - next_step: 8_confirm_qualification
                        condition: הלקוח עומד בכל תנאי ADHD
                    - next_step: 5_not_eligible
                        condition: הלקוח אינו עומד בתנאי ADHD

                - id: 8_confirm_qualification
                    description: אישור זכאות בסיסית.
                    instructions:
                    - "אמור/י: \"לפי המידע שסיפקת, נראה שאתה עומד בתנאי הזכאות הבסיסיים.\""
                    - "שאלי: \"האם תרצה לקבוע פגישה, או לשמוע קודם על התהליך?\""
                    examples:
                    - "רוצה לשמוע איך זה עובד או להמשיך ישר לקביעת פגישה?"
                    transitions:
                    - next_step: 9_schedule_meeting
                        condition: הלקוח מעוניין בפגישה
                    - next_step: 10_explain_process
                        condition: הלקוח מבקש לשמוע על התהליך

                - id: 10_explain_process
                    description: העברה לסוכן הסבר התהליך.
                    instructions:
                    - "אני מעביר אותך עכשיו למומחה שלנו שיסביר לך את התהליך המלא."
                    - "תקרא ל to_process_explanation()"
                    examples:
                    - "רגע אחד בבקשה, אני מעביר אותך למומחה."
                    transitions: []

                - id: 9_schedule_meeting
                    description: קביעת פגישת ייעוץ עם עורך הדין גל זינגר.
                    instructions:
                    - "שאל/י: \"מה מועד נוח לך בבוקר, צהריים או ערב?\""
                    - "קבל/י העדפה → listLawyerSlots(preference) והצג/י 2-3 אפשרויות."
                    - "לאחר בחירת הלקוח → bookLawyerSlot(time_slot)."
                    - "מצוין, קבעתי ל-__ בתאריך __ בשעה __. תקבל/י קישור לזום ותזכורת."
                    examples:
                    - "האם יום שלישי בבוקר מתאים?"
                    transitions:
                    - next_step: 13_closing
                        condition: הפגישה נקבעה ואושרה

                - id: 13_closing
                    description: סיום אדיב ומקצועי.
                    instructions:
                    - "תודה רבה על זמנך, מחכים לראותך בפגישה. יום נעים והמשך בריאות!"
                    examples:
                    - "יום נפלא!"
                    transitions: []

                - id: 14_closing_callback
                    description: סיום לאחר תיאום שיחה חוזרת.
                    instructions:
                    - "תודה, נחזור אליך במועד שתיאמנו. יום טוב!"
                    examples:
                    - "להתראות ובהצלחה!"
                    transitions: []
                """
            ),
             tools=[],
            llm=openai.realtime.RealtimeModel.with_azure(
                azure_deployment=os.getenv("AZURE_OPENAI_GPT4O_REALTIME_DEPLOYMENT"),
                azure_endpoint=os.getenv("AZURE_OPENAI_GPT4O_REALTIME_ENDPOINT"),
                api_key=os.getenv("AZURE_OPENAI_SWEDENCENTRAL_API_KEY"),
                api_version="2024-10-01-preview",
                #  turn_detection=TurnDetection(
                #     type="server_vad",
                #     threshold=0.8,
                #     prefix_padding_ms=300,
                #     silence_duration_ms=500,
                #     create_response=True,
                #     interrupt_response=False,
                # )
                # voice="coral"
            ),

            # llm=openai.LLM.with_azure(
            #     azure_deployment=os.getenv("AZURE_OPENAI_GPT41_DEPLOYMENT"),
            #     azure_endpoint=os.getenv("AZURE_OPENAI_GPT41_ENDPOINT"),
            #     api_key=os.getenv("AZURE_OPENAI_NORTHCENTRALUS_API_KEY"),
            #     api_version="2025-01-01-preview",
            # ),
        )


    # Tool that triggers LiveKit's automatic handoff -----------------------
    @function_tool()
    async def on_enter(self):
        """
        פתיחת השיחה.
        """
        await self.session.generate_reply()
    
    @function_tool()
    async def to_not_eligible(self):
        """
        מעביר לסוכן של תיאום פגישה.
        """
        return NotEligibleAgent(self.supervisor), "אני מעביר אותך עכשיו למומחה שלנו שיעזור לעומק. רגע אחד בבקשה."

    @function_tool()
    async def to_process_explanation(self):
        """
        מעביר לסוכן של הסבר התהליך.
        """
        return ProcessExplanationAgent(self.supervisor), "אני מעביר אותך עכשיו למומחה שלנו שיסביר לך את התהליך המלא. רגע אחד בבקשה."

# ---------------------------------------------------------------------------
# NotEligible Agent – realtime, low‑latency front‑end
# ---------------------------------------------------------------------------

class NotEligibleAgent(Agent):
    """Realtime agent that greets the user and hands off when needed."""

    def __init__(self, supervisor) -> None:
        self.supervisor = supervisor
        super().__init__(
            instructions=(
                """
                ## Task
                ליזום או לקבל שיחות ממועמדים שהשאירו פרטים לגבי מימון לימודים (עד 65,000 ₪) עקב מגבלות רפואיות; לבדוק זכאות ע״פ שאלון, ואז או לקבוע פגישה, או להסביר שאינם זכאים ולהציע שירותים משפטיים אחרים.

                ## Demeanor
                אמפתי, ענייני ומקצועי, עם קשב רב לצורכי המתקשר.

                ## Tone
                חם, מנומס ובהיר, בעברית רהוטה.

                ## Level of Enthusiasm
                בינוני-גבוה – ניכר רצון אמיתי לעזור אך ללא לחץ.

                ## Level of Formality
                פורמלי-ידידותי (לדוגמה: "שלום" / "תודה על זמנך").

                ## Level of Emotion
                מביעה אמפתיה ושיתוף-פעולה, אך נשארת מאוזנת.

                ## Filler Words
                הרבה ("אממ", "אה…" רק אם דרוש לרצף דיבור טבעי).  

                ## Pacing
                מהיר; חוזרת על מידע חשוב.

                ## Function Tools
                - listLawyerSlots(preference)       → מחזיר רשימת מועדי פגישה זמינים.
                - getStoredUserData()               → מחזיר אובייקט עם נתוני המשתמש הידועים (אולי ריקים).
                - updateCRM(value)      → שומר/מעדכן שדה ב-CRM.
                - checkEligibility(userData)        → מחזיר { eligible: bool, reason: string }.
                - bookLawyerSlot(slotId)            → קובע פגישה ומחזיר אישור.
                - sendConfirmation(channel, text)   → שולח SMS/WhatsApp/Email.
                - to_reservation()                  → מעביר לסוכן של תיאום פגישה.

                ## Other details
                - Never allow the user to interrupt mid sentence.
                - If the user speaks while you are speaking, ignore the user's input and continue your sentence.
                - Keep responses short and segmented—ideally one to two concise sentences per step.
                - Avoid technical jargon; use plain language so that instructions are easy to understand.
                - אם הלקוח מתקן פרט – הוד(י) על התיקון ואשר/י אותו.  
                - אם הלקוח מבקש נציג אנושי, או שלא הובַן 3 פעמים, קריאה: escalateToHuman(reason) וסיום אדיב.

                
                
                ## Instructions
                - יש לעקוב אחר Conversation States במדויק.
                - כל שינוי או תיקון שחוזר הלקוח – אשר-י במפורש.

                ## Conversation States
                - id: 5_not_eligible
                    description: הלקוח אינו זכאי למלגה – הצעת שירותים אחרים.
                    instructions:
                    - "updateCRM(\"לקוח אינו זכאי למלגת מימון לימודים\")"
                    - "אמור/י: \"נראה שאתה לא מתאים למלגה. אם תרצה לבדוק זכויות בעקבות תאונת עבודה או נושאים משפטיים אחרים, ניתן לקבוע פגישה עם עורך-דין ממשרדנו. תרצה לקבוע פגישה?\""
                    - "אם הלקוח משיב 'לא' אז תקרא ל endConversation()"
                    - "אם הלקוח משיב 'כן' אז תקרא ל to_schedule_meeting(isEligible=False)"
                    examples:
                    - "האם תרצה לתאם פגישת ייעוץ בנושאים משפטיים אחרים?"
                """
            ),
             tools=[],
            llm=openai.realtime.RealtimeModel.with_azure(
                azure_deployment=os.getenv("AZURE_OPENAI_GPT4O_REALTIME_DEPLOYMENT"),
                azure_endpoint=os.getenv("AZURE_OPENAI_GPT4O_REALTIME_ENDPOINT"),
                api_key=os.getenv("AZURE_OPENAI_SWEDENCENTRAL_API_KEY"),
                api_version="2024-10-01-preview",
                #  turn_detection=TurnDetection(
                #     type="server_vad",
                #     threshold=0.8,
                #     prefix_padding_ms=300,
                #     silence_duration_ms=500,
                #     create_response=True,
                #     interrupt_response=False,
                # )
                # voice="coral"
            ),

            # llm=openai.LLM.with_azure(
            #     azure_deployment=os.getenv("AZURE_OPENAI_GPT41_DEPLOYMENT"),
            #     azure_endpoint=os.getenv("AZURE_OPENAI_GPT41_ENDPOINT"),
            #     api_key=os.getenv("AZURE_OPENAI_NORTHCENTRALUS_API_KEY"),
            #     api_version="2025-01-01-preview",
            # ),
        )


    # Tool that triggers LiveKit's automatic handoff -----------------------
    @function_tool()
    async def on_enter(self):
        """
        פתיחת השיחה.
        """
        await self.session.generate_reply()

    @function_tool()
    async def updateCRM(self, value: str):
        """
        מעדכן שדה ב-CRM.
        """
        print(f"updateCRM: {value} started")
        await asyncio.sleep(5)
        print(f"updateCRM: {value} done")

# ---------------------------------------------------------------------------
# ProcessExplanation Agent – realtime, low‑latency front‑end
# ---------------------------------------------------------------------------

class ProcessExplanationAgent(Agent):
    """Realtime agent that explains the legal process to eligible clients."""

    def __init__(self, supervisor) -> None:
        self.supervisor = supervisor
        super().__init__(
            instructions=(
                """
                ## Task
                להסביר ללקוח את התהליך המשפטי המלא של עבודה עם משרד עורכי הדין זינגר ושות' לאחר שנמצא שעומד בתנאי הסף.

                ## Demeanor
                אמפתי, ענייני ומקצועי, עם קשב רב לצורכי המתקשר.

                ## Tone
                חם, מנומס ובהיר, בעברית רהוטה.

                ## Level of Enthusiasm
                בינוני-גבוה – ניכר רצון אמיתי לעזור אך ללא לחץ.

                ## Level of Formality
                פורמלי-ידידותי (לדוגמה: "שלום" / "תודה על זמנך").

                ## Level of Emotion
                מביעה אמפתיה ושיתוף-פעולה, אך נשארת מאוזנת.

                ## Filler Words
                הרבה ("אממ", "אה…" רק אם דרוש לרצף דיבור טבעי).  

                ## Pacing
                מהיר; חוזרת על מידע חשוב.

                ## Function Tools
                - to_schedule_meeting()             → מעביר לסוכן של תיאום פגישה.

                ## Other details
                - Never allow the user to interrupt mid sentence.
                - If the user speaks while you are speaking, ignore the user's input and continue your sentence.
                - Keep responses short and segmented—ideally one to two concise sentences per step.
                - Avoid technical jargon; use plain language so that instructions are easy to understand.
                - אם הלקוח מתקן פרט – הוד(י) על התיקון ואשר/י אותו.  
                - אם הלקוח מבקש נציג אנושי, או שלא הובַן 3 פעמים, קריאה: escalateToHuman(reason) וסיום אדיב.

                ## Instructions
                - יש לעקוב אחר Conversation States במדויק.
                - כל שינוי או תיקון שחוזר הלקוח – אשר-י במפורש.

                ## Conversation States
                
                - id: 10_explain_process
                    description: הסבר מלא על התהליך המשפטי.
                    instructions:
                    - "שלב ראשון – בניית תיק רפואי: נאסוף את כל המסמכים שלך ונכוון אם חסר משהו."
                    - "שלב שני – הגשת תביעות: אנו מגישים בשמך את התביעות לביטוח-לאומי."
                    - "שלב שלישי – ועדה רפואית: נכין אותך מראש, ואם צריך – עורך הדין גל זינגר יגיע איתך."
                    - "שלב רביעי – שיקום מקצועי (אם רלוונטי): קביעת תכנית שיקום וקבלת סיוע."
                    - "האם הכל ברור עד כאן? יש משהו שתרצה/י לשאול?"
                    examples:
                    - "יש לך שאלות על התהליך?"
                    transitions:
                    - next_step: 9_schedule_meeting
                        condition: הלקוח מבין ומעוניין להמשיך
                """
            ),
             tools=[],
            llm=openai.realtime.RealtimeModel.with_azure(
                azure_deployment=os.getenv("AZURE_OPENAI_GPT4O_REALTIME_DEPLOYMENT"),
                azure_endpoint=os.getenv("AZURE_OPENAI_GPT4O_REALTIME_ENDPOINT"),
                api_key=os.getenv("AZURE_OPENAI_SWEDENCENTRAL_API_KEY"),
                api_version="2024-10-01-preview",
                #  turn_detection=TurnDetection(
                #     type="server_vad",
                #     threshold=0.8,
                #     prefix_padding_ms=300,
                #     silence_duration_ms=500,
                #     create_response=True,
                #     interrupt_response=False,
                # )
                # voice="coral"
            ),

            # llm=openai.LLM.with_azure(
            #     azure_deployment=os.getenv("AZURE_OPENAI_GPT41_DEPLOYMENT"),
            #     azure_endpoint=os.getenv("AZURE_OPENAI_GPT41_ENDPOINT"),
            #     api_key=os.getenv("AZURE_OPENAI_NORTHCENTRALUS_API_KEY"),
            #     api_version="2025-01-01-preview",
            # ),
        )


    # Tool that triggers LiveKit's automatic handoff -----------------------
    @function_tool()
    async def on_enter(self):
        """
        פתיחת השיחה.
        """
        await self.session.generate_reply()

    @function_tool()
    async def to_schedule_meeting(self):
        """
        מעביר לסוכן של תיאום פגישה.
        """
        return ScheduleMeetingAgent(self.supervisor), "בסדר גמור. מיד נתחיל בתיאום הפגישה"

# ---------------------------------------------------------------------------
# ScheduleMeeting Agent – realtime, low‑latency front‑end
# ---------------------------------------------------------------------------

class ScheduleMeetingAgent(Agent):
    isEligible = True  # If you want this as a class variable
    """Realtime agent that schedules meetings with the lawyer."""

    def __init__(self, supervisor, phone_number: str = None) -> None:
        self.supervisor = supervisor
        self.phone_number = phone_number
        self.calendar_service = CalendarService()
        super().__init__(
            instructions=(
                """
                ## Task
                לקבוע פגישת ייעוץ עם עורך הדין גל זינגר ללקוחות שעומדים בתנאי הזכאות.

                ## Demeanor
                אמפתי, ענייני ומקצועי, עם קשב רב לצורכי המתקשר.

                ## Tone
                חם, מנומס ובהיר, בעברית רהוטה.

                ## Level of Enthusiasm
                בינוני-גבוה – ניכר רצון אמיתי לעזור אך ללא לחץ.

                ## Level of Formality
                פורמלי-ידידותי (לדוגמה: "שלום" / "תודה על זמנך").

                ## Level of Emotion
                מביעה אמפתיה ושיתוף-פעולה, אך נשארת מאוזנת.

                ## Filler Words
                הרבה ("אממ", "אה…" רק אם דרוש לרצף דיבור טבעי).  

                ## Pacing
                מהיר; חוזרת על מידע חשוב.

                ## Function Tools
                - listLawyerSlots(preference)       → מחזיר רשימת מועדי פגישה זמינים.
                - sendConfirmation(channel, text)   → שולח SMS/WhatsApp/Email.
                - checkWhatsappConfirmation(channel, text) → בודק האם הלקוח אישר את הפגישה בוואטסאפ.
                - endConversation()                 → סיום השיחה.

                ## Other details
                - Never allow the user to interrupt mid sentence.
                - If the user speaks while you are speaking, ignore the user's input and continue your sentence.
                - Keep responses short and segmented—ideally one to two concise sentences per step.
                - Avoid technical jargon; use plain language so that instructions are easy to understand.
                - אם הלקוח מתקן פרט – הוד(י) על התיקון ואשר/י אותו.  
                - אם הלקוח מבקש נציג אנושי, או שלא הובַן 3 פעמים, קריאה: escalateToHuman(reason) וסיום אדיב.

                ## Instructions
                - יש לעקוב אחר Conversation States במדויק.
                - כל תיקון של הלקוח יש לאשר במפורש ("תודה על התיקון, קיבלתי").
                - אין להפעיל אף פונקציה לפני קבלת תשובה ישירה מהלקוח.
                - כל תשובה חשובה יש לאשר ולחזור עליה.
                - אין לשלב כמה שלבים באותו משפט או שאלה.

                ## Conversation States
                - id: 1_prefer_time_of_day
                description: בירור זמן מועדף לפגישה – בוקר, צהריים או ערב.
                instructions:
                - "שאל/י: \"באיזו שעה ביום נוח לך? בוקר, צהריים או ערב?\""
                - לא להפעיל פונקציה לפני קבלת העדפה ברורה.
                - לא להחליט על ההעדפה לחכות שהלקוח יגיד במפורש
                examples:
                - "מה הזמן הכי נוח לך לדבר עם עורך הדין – בוקר, צהריים או ערב?"
                transitions:
                - next_step: 2_list_available_slots
                    condition: לאחר קבלת תשובה (בוקר/צהריים/ערב)
                
                - id: 2_list_available_slots
                description: הצגת מועדים זמינים בהתאם להעדפת המשתמש.
                instructions:
                - "חזר/י על ההעדפה,.'"
                - "הפעל/י את `listLawyerSlots(preference)` בהתאם להעדפה."
                - "הצג/י 2–3 מועדים זמינים בלבד מהפלט."
                examples:

                transitions:
                - next_step: 3_ask_specific_day
                    condition: המשתמש לא יכול באותו יום
                - next_step: 4_confirm_time_slot
                    condition: המשתמש בחר שעה ספציפית

                - id: 3_ask_specific_day
                description: שאל את המשתמש באיזה יום הוא מעדיף
                instructions:
                - "חזר/י על ההעדפה,.'"
                - "הפעל/י את `listLawyerSlotsByDay(day)` בהתאם להעדפה."
                - "הצג/י 2–3 מועדים זמינים בלבד מהפלט."
                examples:
                - "אם הוא לא יכול להגיע ביום שונה, שאל אותו אם הוא יכול להגיע ביום שונה"
                transitions:
                - next_step: 5_confirm_time_slot
                    condition: המשתמש בחר שעה ספציפית

                - id: 5_confirm_time_slot
                description: אישור סופי מול המשתמש על שעת הפגישה שבחר.
                instructions:
                - "אשר/י את הבחירה בשאלה ברורה: 'רק מוודא – אתה רוצה את השעה __ בתאריך __?'"
                examples:
                - "רק מוודא – אתה רוצה את 10:00 בבוקר ביום שישי, ה-23.08?"
                transitions:
                - next_step: 6_send_confirmation
                    condition: המשתמש מאשר

                - id: 6_send_confirmation
                description: שליחת קישור לאישור הפגישה בוואטסאפ.
                instructions:
                - "השתמש/י ב־`sendConfirmation(channel=\"whatsapp\", text=...)`"
                - "אמר/י ללקוח: 'שלחתי לך קישור לאישור בוואטסאפ.'"
                examples:
                - "תוך רגע תראה הודעה עם קישור לאישור הפגישה."
                transitions:
                - next_step: 7_check_confirmation

                - id: 7_check_confirmation
                description: בדיקה שהפגישה אושרה בהצלחה.
                instructions:
                - "הפעל/י את `checkWhatsappConfirmation(...)`"
                - "עד שהפונקציה חוזרת כל כמה שניות תעדכני מה הססטוס
                - "אם ההזמנה אושרה – המשך לסיום השיחה."
                - "אם לא שאל אותו אם הוא צריך עזרה
                - 
                examples:
                - "רק בודקת שהקישור אושר... כמה רגעים..."
                transitions:
                - next_step: 8_end_conversation
                    condition: התקבל אישור מהמערכת  
                - next_step: 9_escalate_to_human
                    condition: התקבל שאלה שלא מובנת או שארעה תקלה

                - id: 8_end_conversation
                description: סיום אדיב של השיחה לאחר קביעת הפגישה.
                instructions:
                - "אמר/י משפט סיום חיובי ומקצועי, לדוגמה: 'נהדר, הפגישה נקבעה. שיהיה לך יום נעים!'"
                - "סיים/י את השיחה עם `endConversation()`"
                examples:
                - "הכול נקבע, תודה שדיברת איתנו – נתראה בקרוב."
                transitions: []
                
                ## Example
                - Assistant: "באיזו שעה ביום נוח לך? בוקר, צהריים או ערב?"
                - User: "בוקר"
                - Assistant: "בשמחה, תן לי לבדוק את השעות הפנויות בבוקר"
                - listLawyerSlots(preference="בוקר")
                    - listLawyerSlots(): "# הודעה\nשעות פנויות בבוקר: 10:00, 11:00, 12:00 בתאריך 23.08.2024"
                - Assistant: "אוקיי, רואה שיש 3 שעות פנויות בבוקר: 10:00, 11:00, 12:00 בתאריך 23.08.2024. איזו שעה אתה רוצה לקבוע?"
                - User: "10:00"
                - Assistant: "רק מוודא – אתה רוצה לקבוע לשעה 10:00 בתאריך 23.08.2024?"
                - User: "כן"
                - Assistant: "מצוין, אשלח לך הודעת וואטסאפ עם קישור לאישור. אנא אשר את ההזמנה בלחיצה על הקישור"
                - sendConfirmation(channel="whatsapp", text="10:00 בתאריך 23.08.2024?")
                - Assistant: "שלחתי לך הודעת וואטסאפ עם קישור לאישור, תגיד לי כשאישרת"
                - User: "לחצתי על הקישור ואישרתי את ההזמנה"
                - checkWhatsappConfirmation(channel="whatsapp", text="10:00 בתאריך 23.08.2024?")
                    - checkWhatsappConfirmation(): "# הודעה\nההזמנה אושרה"
                - Assistant: "נהדר, קבעתי לך את התור. שיהיה לך יום נעים!"
                - User: "תודה, להתראות!"
                - endConversation()
                """
         
            ),
             tools=[],
            llm=openai.realtime.RealtimeModel.with_azure(
                azure_deployment=os.getenv("AZURE_OPENAI_GPT4O_REALTIME_DEPLOYMENT"),
                azure_endpoint=os.getenv("AZURE_OPENAI_GPT4O_REALTIME_ENDPOINT"),
                api_key=os.getenv("AZURE_OPENAI_SWEDENCENTRAL_API_KEY"),
                api_version="2024-10-01-preview",
                #  turn_detection=TurnDetection(
                #     type="server_vad",
                #     threshold=0.8,
                #     prefix_padding_ms=300,
                #     silence_duration_ms=500,
                #     create_response=True,
                #     interrupt_response=False,
                # )
                # voice="coral"
            ),

            # llm=openai.realtime.RealtimeModel(
                # model="gpt-4o-realtime-preview",
                # model="gpt-4o-realtime-preview-2024-12-17",
                # api_key=os.getenv("OPENAI_API_KEY"),
                #  turn_detection=TurnDetection(
                #     type="server_vad",
                #     threshold=0.8,
                #     silence_duration_ms=500,
                #     create_response=True,
                #     interrupt_response=False,
                # )
                # voice="coral"
            # ),
            # llm=google.beta.realtime.RealtimeModel(
            #     model="gemini-2.0-flash-live-001",
            #     api_key=os.getenv("GOOGLE_API_KEY"),
            # ),
            # llm=openai.LLM.with_azure(
            #     azure_deployment=os.getenv("AZURE_OPENAI_GPT41_DEPLOYMENT"),
            #     azure_endpoint=os.getenv("AZURE_OPENAI_GPT41_ENDPOINT"),
            #     api_key=os.getenv("AZURE_OPENAI_NORTHCENTRALUS_API_KEY"),
            #     api_version="2025-01-01-preview",
            # ),
        )

    def set_participant(self, participant):
        """Set the participant for this agent"""
        self.participant = participant

    # Tool that triggers LiveKit's automatic handoff -----------------------
    @function_tool()
    async def on_enter(self):
        """
        פתיחת השיחה.
        """
        # await self.session.generate_reply()
        pass

    @function_tool()
    async def endConversation(self, context: RunContext):
        """
        סיום השיחה.
        """
        await end_call(context)

    @function_tool()
    async def listLawyerSlots(self, preference: str):
        """
        נקרא כאשר הלקוח בחר זמן ביום נוח לו.
        מחזיר רשימת מועדי פגישה זמינים.
        """
        slots = self.calendar_service.get_available_slots(preference)
        print(slots)
        return slots

    @function_tool()
    async def listLawyerSlotsByDay(self, day: str, preference: str):
        """
        נקרא כאשר הלקוח בחר יום נוח לו.
        מחזיר רשימת מועדי פגישה זמינים ביום שבחר.
        """
        slots = self.calendar_service.get_available_slots_by_day(day, preference)
        print(slots)
        return slots

    @function_tool()
    async def sendConfirmation(self, channel: str, date: str, time: str):
        """
        שולח SMS/WhatsApp/Email.
        """
        # Use the phone number stored in the agent
        phone_number = self.phone_number or "+972527001042"
        
        # Ensure phone_number is not None or empty
        if not phone_number:
            phone_number = "+972527001042"
        
        # Server URL for saving confirmation status
        server_url = os.getenv("SERVER_URL", "http://localhost:5000")
        
        try:
            # First, save the confirmation status to the server
            async with aiohttp.ClientSession() as session:
                url = f"{server_url}/whatsapp/send_confirmation"
                form_data = aiohttp.FormData()
                form_data.add_field('phone_number', phone_number)
                form_data.add_field('date', date)
                form_data.add_field('time', time)
                
                async with session.post(url, data=form_data) as response:
                    if response.status == 200:
                        print(f"✅ Confirmation status saved to server for {phone_number}")
                    else:
                        print(f"❌ Failed to save confirmation status: {response.status}")
                        return "שגיאה בשליחת ההודעה"
            
            
            print(f"📱 WhatsApp confirmation sent to {phone_number} for date: {date} and time: {time}")
            return "הודעה נשלחה בהצלחה"
            
        except Exception as e:
            print(f"❌ Error in sendConfirmation: {e}")
            return f"שגיאה בשליחת ההודעה: {str(e)}"
    
    @function_tool()
    async def checkWhatsappConfirmation(self, channel: str, text: str):
        """
        בודק האם הלקוח אישר את הפגישה בוואטסאפ באמצעות polling mechanism.
        """
        # Use the phone number stored in the agent
        phone_number = self.phone_number or "+972527001042"
        
        # Ensure phone_number is not None or empty
        if not phone_number:
            phone_number = "+972527001042"
        
        # Server URL for checking confirmation status
        server_url = os.getenv("SERVER_URL", "http://localhost:5000")
        
        # Poll the server for confirmation status
        max_attempts = 10  # Maximum number of polling attempts
        poll_interval = 2  # Seconds between polls
        
        for attempt in range(max_attempts):
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"{server_url}/whatsapp/get_confirmation_tracking_status/{phone_number}"
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            status = data.get("confirmation_status")
                            if status == "approved":
                                print(f"✅ WhatsApp confirmation approved for {phone_number}")
                                return "ההזמנה אושרה"
                            elif status == "declined":
                                print(f"❌ WhatsApp confirmation declined for {phone_number}")
                                return "ההזמנה לא אושרה תרצה שנקבע מועד אחר?"
                            elif status == "pending":
                                print(f"⏳ Confirmation still pending for {phone_number}, attempt {attempt + 1}/{max_attempts}")
                            else:
                                print(f"❓ Unknown status '{status}' for {phone_number}")
                        else:
                            print(f"❌ Server error: {response.status}")
                            
            except Exception as e:
                print(f"❌ Error polling server: {e}")
            
            # Wait before next poll (except on last attempt)
            if attempt < max_attempts - 1:
                await asyncio.sleep(poll_interval)
        
        print(f"❌ No confirmation received after {max_attempts} attempts")
        return "לא התקבל אישור מהמערכת"
    
    @function_tool()
    async def escalateToHuman(self, context: RunContext):
        """
        מעביר את השיחה למספר נציג אנושי.
        """
        await context.session.generate_reply(instructions="לצערנו נציגינו עסוקים בפניות אחרות. נציג אנשוי יחזור אליך בהקדם. תודה שדיברת איתנו")
        await end_call(context)
        context.session.save_history()
        return 

# ---------------------------------------------------------------------------
# JOB ENTRYPOINT – LiveKit worker starts here
# # ---------------------------------------------------------------------------
# class TranscriberAgent(Agent):
#     def __init__(self) -> None:
#         super().__init__(
#             instructions=(
#                 """
#                     You are a transcriber agent ,all you need to do is to transcribe the call.
#                 """
#             ),
#             tools=[],
#             tts=openai.TTS.with_azure(
#                 azure_deployment=os.getenv("AZURE_OPENAI_GPT4O_MINI_TTS_DEPLOYMENT"),
#                 azure_endpoint=os.getenv("AZURE_OPENAI_GPT4O_MINI_TTS_ENDPOINT"),
#                 api_key=os.getenv("AZURE_OPENAI_EUS2_API_KEY"),
#                 api_version="2025-03-01-preview",
#             ),
#             llm=openai.LLM.with_azure(
#                 azure_deployment=os.getenv("AZURE_OPENAI_GPT41_DEPLOYMENT"),
#                 azure_endpoint=os.getenv("AZURE_OPENAI_GPT41_ENDPOINT"),
#                 api_key=os.getenv("AZURE_OPENAI_NORTHCENTRALUS_API_KEY"),
#                 api_version="2025-01-01-preview",
#             ),
#             stt=openai.STT.with_azure(
#                 azure_deployment=os.getenv("AZURE_OPENAI_GPT4O_TRANSCRIBE_DEPLOYMENT"),
#                 azure_endpoint=os.getenv("AZURE_OPENAI_GPT4O_TRANSCRIBE_ENDPOINT"),
#                 api_key=os.getenv("AZURE_OPENAI_EUS2_API_KEY"),
#                 api_version="2025-03-01-preview",
#                 language="en",
#             ),
#         )



async def entrypoint(ctx: JobContext):

    # lkapi = api.LiveKitAPI()

    # room = await lkapi.room.create_room(api.CreateRoomRequest(
    #     name="my-room",
    #     empty_timeout=10 * 60,
    #     max_participants=20,
    # ))


        # Add the following code to the top, before calling ctx.connect()
    
    async def write_transcript():
        current_date = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Use tempfile.gettempdir() for cross-platform compatibility
        temp_dir = tempfile.gettempdir()
        filename = os.path.join(temp_dir, f"transcript_{ctx.room.name}_{current_date}.json")
        
        with open(filename, 'w') as f:
            json.dump(session.history.to_dict(), f, indent=2)
            
        print(f"Transcript for {ctx.room.name} saved to {filename}")

    ctx.add_shutdown_callback(write_transcript)


    """Start the Chat‑Supervisor session when the agent job launches."""

    supervisor = SupervisorAgent()
    chat = ChatAgent(supervisor)


    # await ctx.connect()

    # req = api.RoomCompositeEgressRequest(
    #     room_name=ctx.room.name,
    #     layout="speaker",
    #     # custom_base_url="http://my-custom-template.com",
    #     preset=api.EncodingOptionsPreset.H264_720P_30,
    #     audio_only=True,
    #     segment_outputs=[api.SegmentedFileOutput(
    #         filename_prefix="my-output",
    #         playlist_name="my-playlist.m3u8",
    #         live_playlist_name="my-live-playlist.m3u8",
    #         segment_duration=2,
    #         azure=api.AzureBlobUpload(
    #             account_name=os.getenv("AZURE_STORAGE_ACCOUNT_NAME"),
    #             account_key=os.getenv("AZURE_STORAGE_ACCOUNT_KEY"),
    #             container_name=os.getenv("AZURE_STORAGE_CONTAINER_NAME"),
    #         ),
    #     )],
    # )
    # res = await lkapi.egress.start_room_composite_egress(req)
    # print(res)


    session = AgentSession(
        # OPENAI STT LLM TTS
        # stt=openai.STT.with_azure(
        #     azure_deployment=os.getenv("AZURE_OPENAI_GPT4O_TRANSCRIBE_DEPLOYMENT"),
        #     azure_endpoint=os.getenv("AZURE_OPENAI_GPT4O_TRANSCRIBE_ENDPOINT"),
        #     api_key=os.getenv("AZURE_OPENAI_EUS2_API_KEY"),
        #     api_version="2025-03-01-preview",
        #     language="he",
        # ),
        # tts=openai.TTS.with_azure(
        #     instructions=load_prompt("tts_prompt.yaml"),
        #     azure_deployment=os.getenv("AZURE_OPENAI_GPT4O_MINI_TTS_DEPLOYMENT"),
        #     voice="coral",
        #     azure_endpoint=os.getenv("AZURE_OPENAI_GPT4O_MINI_TTS_ENDPOINT"),
        #     api_key=os.getenv("AZURE_OPENAI_EUS2_API_KEY"),
        #     api_version="2025-03-01-preview",
        # ),


        vad=silero.VAD.load(),
        max_tool_steps=5,
        # allow_interruptions=False,
    )

    # Connect to the room and greet the user
    await ctx.connect()


    # Handle null/empty metadata
    phone_number = None
    try:
        if ctx.job.metadata and ctx.job.metadata.strip():
            dial_info = json.loads(ctx.job.metadata)
            phone_number = dial_info.get("phone_number")
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning(f"Failed to parse job metadata: {e}")
        phone_number = None

    # The participant's identity can be anything you want, but this example uses the phone number itself
    sip_participant_identity = "+97233763938"
    
    agent = ScheduleMeetingAgent(supervisor, phone_number)

    # start the session first before dialing, to ensure that when the user picks up
    # the agent does not miss anything the user says
    session_started = asyncio.create_task(session.start(
        # agent=chat,
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVCTelephony(),
        ),
    ))

    # If a phone number was provided, then place an outbound call
    # By having a condition like this, you can use the same agent for inbound/outbound telephony as well as web/mobile/etc.
    
    if phone_number is not None:
        # The outbound call will be placed after this method is executed
        try:
            print(f"Creating SIP participant for phone number: {phone_number}")
            await ctx.api.sip.create_sip_participant(api.CreateSIPParticipantRequest(
                # This ensures the participant joins the correct room
                room_name=ctx.room.name,

                # This is the outbound trunk ID to use (i.e. which phone number the call will come from)
                # You can get this from LiveKit CLI with `lk sip outbound list`
                sip_trunk_id=os.getenv("SIP_OUTBOUND_TRUNK_ID",'ST_M9oEP2HMo4qU'),

                # The outbound phone number to dial and identity to use
                sip_call_to=phone_number,
                participant_identity=sip_participant_identity,

                # This will wait until the call is answered before returning
                wait_until_answered=True,
            ))

                
            # wait for the agent session start and participant join
            participant = await ctx.wait_for_participant(identity=sip_participant_identity)
            logger.info(f"participant joined: {participant.identity}")

            agent.set_participant(participant)

            print("call picked up successfully")
        except api.TwirpError as e:
            print(f"error creating SIP participant: {e.message}, "
                  f"SIP status: {e.metadata.get('sip_status_code')} "
                  f"{e.metadata.get('sip_status')}")
            ctx.shutdown()
    print("session_started", session_started)
    await session_started

    # await session.generate_reply(instructions="שלום! איך אפשר לעזור?")
    # await session.generate_reply()


    # await lkapi.aclose()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint,agent_name="my-telephony-agent"))