import asyncio
from datetime import datetime
import logging
import os
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
from agents.common_functions import end_call
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


# ---------------------------------------------------------------------------
# ENV & GLOBALS
# ---------------------------------------------------------------------------
logger = logging.getLogger("restaurant-example")
logger.setLevel(logging.INFO)

load_dotenv()


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
                - to_not_eligible()                  → מעביר לסוכן של תיאום פגישה.
                - to_process_explanation()          → מעביר לסוכן של הסבר התהליך.

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
                    - "אם הלקוח משיב 'כן' אז תקרא ל to_reservation()"
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
    """Realtime agent that schedules meetings with the lawyer."""

    def __init__(self, supervisor) -> None:
        self.supervisor = supervisor
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
                - bookLawyerSlot(slotId)            → קובע פגישה ומחזיר אישור.
                - sendConfirmation(channel, text)   → שולח SMS/WhatsApp/Email.
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
                - כל שינוי או תיקון שחוזר הלקוח – אשר-י במפורש.

                ## Conversation States
                
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
    async def endConversation(self, context: RunContext):
        """
        סיום השיחה.
        """
        await end_call(context)

# ---------------------------------------------------------------------------
# JOB ENTRYPOINT – LiveKit worker starts here
# ---------------------------------------------------------------------------


async def entrypoint(ctx: JobContext):

    # lkapi = api.LiveKitAPI()

    # room = await lkapi.room.create_room(api.CreateRoomRequest(
    #     name="my-room",
    #     empty_timeout=10 * 60,
    #     max_participants=20,
    # ))

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
        stt=openai.STT.with_azure(
            azure_deployment=os.getenv("AZURE_OPENAI_GPT4O_TRANSCRIBE_DEPLOYMENT"),
            azure_endpoint=os.getenv("AZURE_OPENAI_GPT4O_TRANSCRIBE_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_EUS2_API_KEY"),
            api_version="2025-03-01-preview",
            language="he",
        ),
        tts=openai.TTS.with_azure(
            instructions=load_prompt("tts_prompt.yaml"),
            azure_deployment=os.getenv("AZURE_OPENAI_GPT4O_MINI_TTS_DEPLOYMENT"),
            voice="coral",
            azure_endpoint=os.getenv("AZURE_OPENAI_GPT4O_MINI_TTS_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_EUS2_API_KEY"),
            api_version="2025-03-01-preview",
        ),


        vad=silero.VAD.load(),
        max_tool_steps=5,
        # allow_interruptions=False,
    )

    await session.start(
        agent=chat,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVCTelephony(),
        ),
    )

    # Connect to the room and greet the user
    await ctx.connect()
    # await session.generate_reply(instructions="שלום! איך אפשר לעזור?")
    await session.generate_reply()


    # await lkapi.aclose()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))