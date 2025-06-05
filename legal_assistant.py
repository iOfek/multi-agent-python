import logging
from dataclasses import dataclass, field, asdict
from typing import Optional, List
from dotenv import load_dotenv
import json
from datetime import datetime
import os

from livekit import api
from livekit.agents import (
    Agent,
    AgentSession,
    ChatContext,
    JobContext,
    JobProcess,
    RoomInputOptions,
    RoomOutputOptions,
    RunContext,
    WorkerOptions,
    cli,
    metrics,
)
from livekit.agents.job import get_job_context
from livekit.agents.llm import function_tool
from livekit.agents.voice import MetricsCollectedEvent
from livekit.plugins import openai, silero

logger = logging.getLogger("legal-assistant")

load_dotenv(dotenv_path=".env.local")

@dataclass
class ClientData:
    # Basic client information
    name: Optional[str] = None
    age: Optional[int] = None
    is_student: Optional[bool] = None
    student_details: Optional[str] = None
    
    # Employment information
    is_employed: Optional[bool] = None
    employment_duration: Optional[str] = None
    monthly_income: Optional[float] = None
    
    # Medical condition information
    medical_condition: Optional[str] = None
    diagnosis_date: Optional[str] = None
    medications: List[str] = field(default_factory=list)
    treatment_duration: Optional[str] = None
    
    # Eligibility flags
    meets_income_threshold: Optional[bool] = None
    has_continuous_employment: Optional[bool] = None
    has_medical_documentation: Optional[bool] = None

    def to_dict(self):
        return asdict(self)

def save_client_data(client_data: ClientData):
    """Save client data to a JSON file"""
    # Create data directory if it doesn't exist
    os.makedirs('client_data', exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'client_data/client_{timestamp}.json'
    
    # Convert client data to dictionary and save to file
    data = client_data.to_dict()
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved client data to {filename}")
    return filename

class HandoffError(Exception):
    """Custom exception for handoff errors"""
    pass

class DataValidationError(Exception):
    """Custom exception for data validation errors"""
    pass

@dataclass
class StepSummary:
    """Class to hold step summary information"""
    step_name: str
    collected_data: dict
    is_valid: bool
    validation_message: str

def validate_and_summarize_step(context: RunContext[ClientData], step_name: str, required_fields: dict) -> StepSummary:
    """Validate and summarize the current step's data"""
    try:
        # Check for missing fields
        missing_fields = [field for field, value in required_fields.items() if value is None]
        
        # Get current data
        current_data = {field: getattr(context.userdata, field) for field in required_fields.keys()}
        
        if missing_fields:
            return StepSummary(
                step_name=step_name,
                collected_data=current_data,
                is_valid=False,
                validation_message=f"חסרים השדות הבאים: {', '.join(missing_fields)}"
            )
        
        return StepSummary(
            step_name=step_name,
            collected_data=current_data,
            is_valid=True,
            validation_message="כל המידע הנדרש נאסף"
        )
    except Exception as e:
        logger.error(f"Error in validate_and_summarize_step: {str(e)}")
        raise DataValidationError(f"שגיאה בבדיקת המידע: {str(e)}")

class InitialScreeningAgent(Agent):
    def __init__(self, chat_ctx: Optional[ChatContext] = None) -> None:
        super().__init__(
            instructions="""אתה מערכת AI של משרד עורכי הדין זינגר ושות'.
            תפקידך לבצע שיחות טלפון ראשוניות עם לקוחות פוטנציאליים בנוגע למיצוי זכויות מול ביטוח לאומי.
            אתה מדבר רק בעברית.
            מטרתך לאסוף מידע בסיסי ולבדוק אם הלקוח עומד בקריטריונים ראשוניים לזכאות.
            לאחר איסוף המידע הבסיסי, העבר את השיחה למומחה הרפואי.""",
            chat_ctx=chat_ctx
        )

    async def on_enter(self):
        self.session.say()

    @function_tool
    async def collect_basic_info(
        self,
        context: RunContext[ClientData],
        name: str,
        age: int,
        is_student: bool,
        student_details: Optional[str] = None
    ):
        """איסוף מידע בסיסי על הלקוח
        שם הלקוח: {name}
        גיל: {age}
        האם הלקוח סטודנט: {is_student}
        פרטים נוספים על הסטודנט: {student_details}
        """
        try:
            context.userdata.name = name
            context.userdata.age = age
            context.userdata.is_student = is_student
            context.userdata.student_details = student_details
            logger.info(f"Collected basic info for client: {name}, {age}, {is_student}, {student_details}")
            save_client_data(context.userdata)
        except Exception as e:
            logger.error(f"Error collecting basic info: {str(e)}")
            raise DataValidationError(f"שגיאה באיסוף המידע הבסיסי: {str(e)}")

    @function_tool
    async def collect_employment_info(
        self,
        context: RunContext[ClientData],
        is_employed: bool,
        employment_duration: str,
        monthly_income: float
    ):
        """איסוף מידע על תעסוקה"""
        try:
            context.userdata.is_employed = is_employed
            context.userdata.employment_duration = employment_duration
            context.userdata.monthly_income = monthly_income
            logger.info(f"Collected employment info for client: {context.userdata.name}")
            save_client_data(context.userdata)
        except Exception as e:
            logger.error(f"Error collecting employment info: {str(e)}")
            raise DataValidationError(f"שגיאה באיסוף מידע על תעסוקה: {str(e)}")

    @function_tool
    async def handoff_to_medical(
        self,
        context: RunContext[ClientData]
    ):
        """העברת השיחה למומחה הרפואי"""
        try:
            # Define required fields for this step
            required_fields = {
                'name': context.userdata.name,
                'age': context.userdata.age,
                'is_employed': context.userdata.is_employed,
                'employment_duration': context.userdata.employment_duration,
                'monthly_income': context.userdata.monthly_income
            }
            
            # Validate and summarize current step
            summary = validate_and_summarize_step(context, "איסוף מידע בסיסי", required_fields)
            
            if not summary.is_valid:
                return None, f"לפני שנמשיך, {summary.validation_message}"
            
            # Present summary to user
            summary_message = f"""
            הנה סיכום המידע שנאסף עד כה:
            שם: {context.userdata.name}
            גיל: {context.userdata.age}
            עובד: {'כן' if context.userdata.is_employed else 'לא'}
            משך עבודה: {context.userdata.employment_duration}
            הכנסה חודשית: {context.userdata.monthly_income} ש"ח
            
            האם המידע נכון?
            """
            
            # Create new agent with current chat context
            medical_agent = MedicalAssessmentAgent(chat_ctx=context.session._chat_ctx)
            logger.info(f"Handing off to medical assessment for client: {context.userdata.name}")
            return medical_agent, summary_message + "\nאני אעביר אותך עכשיו למומחה הרפואי שלנו"
            
        except Exception as e:
            logger.error(f"Error in handoff to medical: {str(e)}")
            raise HandoffError(f"שגיאה בהעברת השיחה למומחה הרפואי: {str(e)}")

class MedicalAssessmentAgent(Agent):
    def __init__(self, chat_ctx: Optional[ChatContext] = None) -> None:
        super().__init__(
            instructions="""אתה מומחה להערכת מצב רפואי במשרד עורכי הדין זינגר ושות'.
            תפקידך לאסוף מידע מפורט על המצב הרפואי של הלקוח והיסטוריית הטיפול.
            אתה מדבר רק בעברית.
            לאחר איסוף המידע הרפואי, העבר את השיחה למומחה להערכת זכאות.""",
            chat_ctx=chat_ctx
        )

    async def on_enter(self):
        """Automatically start collecting medical information when agent is initialized"""
        self.session.say(
            "שלום, אני המומחה הרפואי. אני אשמח לקבל מידע על המצב הרפואי שלך. אנא ספר לי על המצב הרפואי שלך, מתי אובחנת, אילו תרופות אתה נוטל, וכמה זמן אתה מטופל."
        )

    @function_tool
    async def collect_medical_info(
        self,
        context: RunContext[ClientData],
        condition: str,
        diagnosis_date: str,
        medications: List[str],
        treatment_duration: str
    ):
        """איסוף מידע על מצב רפואי"""
        try:
            context.userdata.medical_condition = condition
            context.userdata.diagnosis_date = diagnosis_date
            context.userdata.medications = medications
            context.userdata.treatment_duration = treatment_duration
            logger.info(f"Collected medical info for client: {context.userdata.name}")
            save_client_data(context.userdata)
        except Exception as e:
            logger.error(f"Error collecting medical info: {str(e)}")
            raise DataValidationError(f"שגיאה באיסוף מידע רפואי: {str(e)}")

    @function_tool
    async def handoff_to_eligibility(
        self,
        context: RunContext[ClientData]
    ):
        """העברת השיחה למומחה להערכת זכאות"""
        try:
            # Define required fields for this step
            required_fields = {
                'medical_condition': context.userdata.medical_condition,
                'diagnosis_date': context.userdata.diagnosis_date,
                'treatment_duration': context.userdata.treatment_duration
            }
            
            # Validate and summarize current step
            summary = validate_and_summarize_step(context, "איסוף מידע רפואי", required_fields)
            
            if not summary.is_valid:
                return None, f"לפני שנמשיך, {summary.validation_message}"
            
            # Present summary to user
            summary_message = f"""
            הנה סיכום המידע הרפואי שנאסף:
            מצב רפואי: {context.userdata.medical_condition}
            תאריך אבחון: {context.userdata.diagnosis_date}
            תרופות: {', '.join(context.userdata.medications)}
            משך טיפול: {context.userdata.treatment_duration}
            
            האם המידע נכון?
            """
            
            # Create new agent with current chat context
            eligibility_agent = EligibilityAssessmentAgent(chat_ctx=context.session._chat_ctx)
            logger.info(f"Handing off to eligibility assessment for client: {context.userdata.name}")
            return eligibility_agent, summary_message + "\nאני אעביר אותך עכשיו למומחה להערכת זכאות"
            
        except Exception as e:
            logger.error(f"Error in handoff to eligibility: {str(e)}")
            raise HandoffError(f"שגיאה בהעברת השיחה להערכת זכאות: {str(e)}")

class EligibilityAssessmentAgent(Agent):
    def __init__(self, chat_ctx: Optional[ChatContext] = None) -> None:
        super().__init__(
            instructions="""אתה מומחה להערכת זכאות במשרד עורכי הדין זינגר ושות'.
            תפקידך להעריך אם הלקוח עומד בקריטריונים הבסיסיים לזכאות לקצבאות ביטוח לאומי.
            אתה מדבר רק בעברית.
            לאחר הערכת הזכאות, העבר את השיחה למומחה לתיאום פגישות אם הלקוח זכאי.""",
            chat_ctx=chat_ctx
        )

    @function_tool
    async def assess_eligibility(
        self,
        context: RunContext[ClientData]
    ):
        """הערכת זכאות הלקוח"""
        try:
            # בדיקת סף הכנסה
            context.userdata.meets_income_threshold = context.userdata.monthly_income < 8000
            
            # בדיקת רציפות תעסוקה
            context.userdata.has_continuous_employment = (
                context.userdata.is_employed and 
                "שנה" in context.userdata.employment_duration
            )
            
            # בדיקת תיעוד רפואי
            context.userdata.has_medical_documentation = (
                context.userdata.medical_condition is not None and
                context.userdata.diagnosis_date is not None
            )
            
            logger.info(f"Assessed eligibility for client: {context.userdata.name}")
            save_client_data(context.userdata)
            return context.userdata
        except Exception as e:
            logger.error(f"Error assessing eligibility: {str(e)}")
            raise DataValidationError(f"שגיאה בהערכת זכאות: {str(e)}")

    @function_tool
    async def handoff_to_scheduling(
        self,
        context: RunContext[ClientData]
    ):
        """העברת השיחה למומחה לתיאום פגישות"""
        try:
            # Present eligibility assessment summary
            summary_message = f"""
            הנה תוצאות הערכת הזכאות:
            סף הכנסה: {'עומד' if context.userdata.meets_income_threshold else 'לא עומד'}
            רציפות תעסוקה: {'עומד' if context.userdata.has_continuous_employment else 'לא עומד'}
            תיעוד רפואי: {'קיים' if context.userdata.has_medical_documentation else 'חסר'}
            """
            
            # Validate eligibility criteria
            if not context.userdata.meets_income_threshold:
                return None, summary_message + "\nלצערי, הכנסתך החודשית גבוהה מדי מכדי להיות זכאי"
            
            if not context.userdata.has_continuous_employment:
                return None, summary_message + "\nלצערי, נדרשת תקופת עבודה רציפה של שנה לפחות"
            
            if not context.userdata.has_medical_documentation:
                return None, summary_message + "\nלצערי, נדרש תיעוד רפואי מפורט יותר"
            
            # Create new agent with current chat context
            scheduling_agent = SchedulingAgent(chat_ctx=context.session._chat_ctx)
            logger.info(f"Handing off to scheduling for eligible client: {context.userdata.name}")
            return scheduling_agent, summary_message + "\nמעולה! נראה שאתה עומד בקריטריונים. אני אעביר אותך עכשיו לתיאום פגישה"
            
        except Exception as e:
            logger.error(f"Error in handoff to scheduling: {str(e)}")
            raise HandoffError(f"שגיאה בהעברת השיחה לתיאום פגישה: {str(e)}")

class SchedulingAgent(Agent):
    def __init__(self, chat_ctx: Optional[ChatContext] = None) -> None:
        super().__init__(
            instructions="""אתה מומחה לתיאום פגישות במשרד עורכי הדין זינגר ושות'.
            תפקידך לתאם פגישות ייעוץ ראשוניות עם עורך הדין.
            אתה מדבר רק בעברית.""",
            chat_ctx=chat_ctx
        )

    @function_tool
    async def schedule_consultation(
        self,
        context: RunContext[ClientData],
        preferred_time: str,
        preferred_date: str
    ):
        """תיאום פגישת ייעוץ"""
        # כאן יהיה הלוגיקה של תיאום הפגישה
        logger.info(f"Scheduled consultation for client: {context.userdata.name}")
        save_client_data(context.userdata)
        return f"פגישה נקבעה לתאריך {preferred_date} בשעה {preferred_time}"

class DataCollectionAgent(Agent):
    def __init__(self, chat_ctx: Optional[ChatContext] = None) -> None:
        super().__init__(
            instructions="""אתה מערכת AI מקצועית שמבצעת איסוף נתונים ראשוני.
            מטרתך לאסוף מידע בסיסי מהלקוח בצורה ידידותית ומקצועית.
            עקוב אחר זרימת השיחה בדיוק כפי שמוגדר, שא-ל שאלה אחת בכל פעם ואשר תשובות.
            שמור תמיד על טון מקצועי ואמפתי.
            אתה מדבר רק בעברית.""",
            chat_ctx=chat_ctx
        )

    async def on_enter(self):
        """Start the conversation with an introduction"""
        self.session.say(
            "שלום! אני העוזר האישי שלך. אני כאן כדי לעזור לך היום. לפני שנתחיל, אשמח להכיר אותך קצת יותר. אפשר לדעת איך קוראים לך?"
        )

    @function_tool
    async def collect_name(
        self,
        context: RunContext[ClientData],
        name: str
    ):
        """Collect and confirm client's name"""
        context.userdata.name = name
        logger.info(f"Collected name: {name}")
        self.session.say(
            f"{name}, תודה ששיתפת אותי. נעים להכיר! האם אתה סטודנט? זה יעזור לי להבין טוב יותר את הצרכים שלך ולספק לך סיוע רלוונטי."
        )

    @function_tool
    async def collect_student_status(
        self,
        context: RunContext[ClientData],
        is_student: bool,
        education_level: Optional[str] = None,
        field_of_study: Optional[str] = None
    ):
        """Collect student status and related information"""
        context.userdata.is_student = is_student
        if is_student:
            context.userdata.student_details = f"{education_level} ב{field_of_study}"
            logger.info(f"Collected student info: {context.userdata.student_details}")
            self.session.say(
                f"תודה ששיתפת. אשמח לשמוע על הרקע המקצועי שלך. באיזה תחום אתה עובד?"
            )
        else:
            self.session.say(
                "אשמח לשמוע על הרקע המקצועי שלך. באיזה תחום אתה עובד?"
            )

    @function_tool
    async def collect_professional_info(
        self,
        context: RunContext[ClientData],
        field: str,
        experience_years: int
    ):
        """Collect professional background information"""
        context.userdata.employment_duration = f"{experience_years} שנים"
        logger.info(f"Collected professional info: {field}, {experience_years} years")
        self.session.say(
            "מה מביא אותך לכאן היום? איזה סוג של סיוע אתה מחפש?"
        )

    @function_tool
    async def collect_primary_goal(
        self,
        context: RunContext[ClientData],
        goal: str
    ):
        """Collect the primary goal of the client"""
        context.userdata.background = goal
        logger.info(f"Collected primary goal: {goal}")
        self.session.say(
            "האם עבדת בעבר עם עוזרים דיגיטליים? זה יעזור לי להתאים את סגנון התקשורת שלי לצרכים שלך."
        )

    @function_tool
    async def collect_ai_experience(
        self,
        context: RunContext[ClientData],
        has_experience: bool
    ):
        """Collect information about previous AI assistant experience"""
        logger.info(f"Collected AI experience: {has_experience}")
        self.session.say(
            "כמה זמן יש לך זמין לפגישה שלנו היום? זה יעזור לי לתעדף את השיחה שלנו."
        )

    @function_tool
    async def collect_time_availability(
        self,
        context: RunContext[ClientData],
        available_minutes: int
    ):
        """Collect information about time availability"""
        logger.info(f"Collected time availability: {available_minutes} minutes")
        self.session.say(
            "האם אתה מעדיף הסברים מפורטים או תשובות תמציתיות? אני רוצה לוודא שאני מתקשר בצורה שמתאימה לך ביותר."
        )

    @function_tool
    async def collect_communication_preference(
        self,
        context: RunContext[ClientData],
        prefers_detailed: bool
    ):
        """Collect communication preference"""
        logger.info(f"Collected communication preference: {'detailed' if prefers_detailed else 'concise'}")
        self.session.say(
            f"תודה ששיתפת את המידע הזה איתי. אני אקח את זה בחשבון כשנעבוד יחד. האם יש משהו ספציפי שתרצה שנתחיל איתו?"
        )

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    await ctx.connect()

    session = AgentSession[ClientData](
        vad=ctx.proc.userdata["vad"],
        stt=openai.STT.with_azure(
            azure_deployment="gpt-4o-transcribe",
            azure_endpoint=r"https://iofek-mbcpsptu-eastus2.cognitiveservices.azure.com/openai/deployments/gpt-4o-transcribe/audio/transcriptions?api-version=2025-03-01-preview",
            api_key="4P3LarHA127RY4jDSABYaG5MA6QV4XrBpsJfK1LkjFOEsqcsTsz9JQQJ99BEACHYHv6XJ3w3AAAAACOGME7w",
            api_version="2025-03-01-preview",
            language="he",
        ),

        llm=openai.LLM.with_azure(
            azure_deployment="gpt-4.1",
            azure_endpoint=r"https://iofek-mbcpsptu-eastus2.cognitiveservices.azure.com/openai/deployments/gpt-4.1/chat/completions?api-version=2025-01-01-preview",
            api_key="4P3LarHA127RY4jDSABYaG5MA6QV4XrBpsJfK1LkjFOEsqcsTsz9JQQJ99BEACHYHv6XJ3w3AAAAACOGME7w",
            api_version="2025-01-01-preview",
        ),
        tts=openai.TTS.with_azure(
            azure_deployment="gpt-4o-mini-tts",
            voice="onyx",
            azure_endpoint=r"https://iofek-mbcpsptu-eastus2.cognitiveservices.azure.com/openai/deployments/gpt-4o-mini-tts/audio/speech?api-version=2025-03-01-preview",
            api_key="4P3LarHA127RY4jDSABYaG5MA6QV4XrBpsJfK1LkjFOEsqcsTsz9JQQJ99BEACHYHv6XJ3w3AAAAACOGME7w",
            api_version="2025-03-01-preview",
        ),
        
        userdata=ClientData(),
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=DataCollectionAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(),
        room_output_options=RoomOutputOptions(transcription_enabled=True),
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm)) 