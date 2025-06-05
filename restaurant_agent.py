from datetime import datetime
import logging
from dataclasses import dataclass, field
from typing import Annotated, Optional, List

import yaml
from dotenv import load_dotenv
from pydantic import Field

from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.llm import function_tool
from livekit.agents.voice import Agent, AgentSession, RunContext
from livekit.agents.voice.room_io import RoomInputOptions
from livekit.plugins import openai, silero
from livekit import api, rtc
from livekit.agents import get_job_context


# from livekit.plugins import noise_cancellation

logger = logging.getLogger("restaurant-example")
logger.setLevel(logging.INFO)

load_dotenv()


@dataclass
class UserData:
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

    # Agent information
    agents: dict[str, Agent] = field(default_factory=dict)
    prev_agent: Optional[Agent] = None

    def summarize(self) -> str:
        data = {
            "name": self.name or "unknown",
            "age": self.age or "unknown",
            "is_student": self.is_student or False,
            "student_details": self.student_details or "unknown",
            "is_employed": self.is_employed or False,
            "employment_duration": self.employment_duration or "unknown",
            "monthly_income": self.monthly_income or "unknown",
            "medical_condition": self.medical_condition or "unknown",
            "diagnosis_date": self.diagnosis_date or "unknown",
            "medications": self.medications or "unknown",
            "treatment_duration": self.treatment_duration or "unknown",
            "meets_income_threshold": self.meets_income_threshold or False,
            "has_continuous_employment": self.has_continuous_employment or False,
            "has_medical_documentation": self.has_medical_documentation or False,
        }
        # summarize in yaml performs better than json
        return yaml.dump(data)


RunContext_T = RunContext[UserData]


# common functions


@function_tool()
async def update_name(
    name: Annotated[str, Field(description="The customer's name")],
    context: RunContext_T,
) -> str:
    """Called when the user provides their name.
    Confirm the spelling with the user before calling the function."""
    userdata = context.userdata
    userdata.customer_name = name
    return f"The name is updated to {name}"


@function_tool()
async def update_phone(
    phone: Annotated[str, Field(description="The customer's phone number")],
    context: RunContext_T,
) -> str:
    """Called when the user provides their phone number.
    Confirm the spelling with the user before calling the function."""
    userdata = context.userdata
    userdata.customer_phone = phone
    return f"The phone number is updated to {phone}"


@function_tool()
async def to_greeter(context: RunContext_T) -> Agent:
    """Called when user asks any unrelated questions or requests
    any other services not in your job description."""
    curr_agent: BaseAgent = context.session.current_agent
    return await curr_agent._transfer_to_agent("greeter", context)

# Add this function definition anywhere
async def hangup_call():
    ctx = get_job_context()
    if ctx is None:
        # Not running in a job context
        return
    
    await ctx.api.room.delete_room(
        api.DeleteRoomRequest(
            room=ctx.room.name,
        )
    )

 # to hang up the call as part of a function call
@function_tool()
async def end_call(context: RunContext_T) -> Agent:
    """נקרא כאשר סיימנו לאסוף את כל הפרטים הנדרשים מהלקוח"""
    # let the agent finish speaking
    current_speech = context.session.current_speech
    if current_speech:
        await current_speech.wait_for_playout()
    await hangup_call()


class BaseAgent(Agent):
    async def on_enter(self) -> None:
        agent_name = self.__class__.__name__
        logger.info(f"entering task {agent_name}")

        userdata: UserData = self.session.userdata
        chat_ctx = self.chat_ctx.copy()

        # add the previous agent's chat history to the current agent
        if isinstance(userdata.prev_agent, Agent):
            truncated_chat_ctx = userdata.prev_agent.chat_ctx.copy(
                exclude_instructions=True, exclude_function_call=False
            ).truncate(max_items=6)
            existing_ids = {item.id for item in chat_ctx.items}
            items_copy = [item for item in truncated_chat_ctx.items if item.id not in existing_ids]
            chat_ctx.items.extend(items_copy)

        # add an instructions including the user data as assistant message
        chat_ctx.add_message(
            role="system",  # role=system works for OpenAI's LLM and Realtime API
            content=f"You are {agent_name} agent. Current user data is {userdata.summarize()}",
        )
        await self.update_chat_ctx(chat_ctx)
        self.session.generate_reply(tool_choice="none")

    async def _transfer_to_agent(self, name: str, context: RunContext_T) -> tuple[Agent, str]:
        userdata = context.userdata
        current_agent = context.session.current_agent
        next_agent = userdata.agents[name]
        userdata.prev_agent = current_agent

        return next_agent, f"Transferring to {name}."


class Ender(BaseAgent):
    def __init__(self, basic_agent_knowledge: str) -> None:
        super().__init__(
            instructions=(
                "את מזכירה ידידותית AI במשרד עורכי הדין זינגר ושות'."
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

        self.session.say("תודה שפנית אליי. בהצלחה!")
        self.session.aclose



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
        self.session.say("שלום, מדברת מערכת זינגר AI ממשרד עורכי הדין זינגר ושות'. אני מתקשרת אליך בעקבות הפנייה שהשארת לנו בנוגע למיצוי זכויות מול ביטוח לאומי. אפשר כמה דקות לדבר? ")


        self.basic_agent_knowledge = basic_agent_knowledge

    @function_tool()
    async def to_reservation(self, context: RunContext_T) -> tuple[Agent, str]:
        """נקרא כאשר המשתמש רוצה לתאם פגישה במועד אחר.
הפונקציה הזו מטפלת במעבר לסוכן התיאומים,
אשר יאסוף את הפרטים הדרושים - תאריך ומעד הפגישה."""
        return await self._transfer_to_agent("reservation", context)

    @function_tool()
    async def to_takeaway(self, context: RunContext_T) -> tuple[Agent, str]:
        """Called when the user wants to place a takeaway order.
        This includes handling orders for pickup, delivery, or when the user wants to
        proceed to checkout with their existing order."""
        return await self._transfer_to_agent("takeaway", context)


class Reservation(BaseAgent):
    def __init__(self, basic_agent_knowledge: str) -> None:
        super().__init__(
            instructions=(
                "את מזכירה ידידותית AI במשרד עורכי הדין זינגר ושות'."
                # "המידע הבסיסי שלך הוא: {basic_agent_knowledge}"
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
        context: RunContext_T,
    ) -> str:
        """נקרא כאשר המשתמש מספק את זמן השיחה הטלפונית.
יש לאשר את הזמן עם המשתמש לפני קריאה לפונקציה."""
        userdata = context.userdata
        userdata.reservation_time = time
        return f"The phone call time is updated to {time}"

    @function_tool()
    async def confirm_reservation(self, context: RunContext_T) -> str | tuple[Agent, str]:
        """נקרא כאשר המשתמש מאשר את זמן השיחה הטלפונית.
יש לאשר את הזמן עם המשתמש לפני קריאה לפונקציה."""
        userdata = context.userdata
        if not userdata.customer_name or not userdata.customer_phone:
            return "אנא ספק את שמך ומספר הטלפון שלך תחילה."

        if not userdata.reservation_time:
            return "אנא ספק תחילה מועד נוח לשיחה הטלפונית. "

        return await self._transfer_to_agent("greeter", context)


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
        items: Annotated[list[str], Field(description="The items of the full order")],
        context: RunContext_T,
    ) -> str:
        """Called when the user create or update their order."""
        userdata = context.userdata
        userdata.order = items
        return f"The order is updated to {items}"

    @function_tool()
    async def to_checkout(self, context: RunContext_T) -> str | tuple[Agent, str]:
        """Called when the user confirms the order."""
        userdata = context.userdata
        if not userdata.order:
            return "No takeaway order found. Please make an order first."

        return await self._transfer_to_agent("checkout", context)


class Checkout(BaseAgent):
    def __init__(self, basic_agent_knowledge: str) -> None:
        super().__init__(
            instructions=(
                f"You are a checkout agent at a restaurant. The basic_agent_knowledge is: {basic_agent_knowledge}\n"
                "Your are responsible for confirming the expense of the "
                "order and then collecting customer's name, phone number and credit card "
                "information, including the card number, expiry date, and CVV step by step."
            ),
            tools=[update_name, update_phone, to_greeter],
        )

    @function_tool()
    async def confirm_expense(
        self,
        expense: Annotated[float, Field(description="The expense of the order")],
        context: RunContext_T,
    ) -> str:
        """Called when the user confirms the expense."""
        userdata = context.userdata
        userdata.expense = expense
        return f"The expense is confirmed to be {expense}"

    @function_tool()
    async def update_credit_card(
        self,
        number: Annotated[str, Field(description="The credit card number")],
        expiry: Annotated[str, Field(description="The expiry date of the credit card")],
        cvv: Annotated[str, Field(description="The CVV of the credit card")],
        context: RunContext_T,
    ) -> str:
        """Called when the user provides their credit card number, expiry date, and CVV.
        Confirm the spelling with the user before calling the function."""
        userdata = context.userdata
        userdata.customer_credit_card = number
        userdata.customer_credit_card_expiry = expiry
        userdata.customer_credit_card_cvv = cvv
        return f"The credit card number is updated to {number}"

    @function_tool()
    async def confirm_checkout(self, context: RunContext_T) -> str | tuple[Agent, str]:
        """Called when the user confirms the checkout."""
        userdata = context.userdata
        if not userdata.expense:
            return "Please confirm the expense first."

        if (
            not userdata.customer_credit_card
            or not userdata.customer_credit_card_expiry
            or not userdata.customer_credit_card_cvv
        ):
            return "Please provide the credit card information first."

        userdata.checked_out = True
        return await to_greeter(context)

    @function_tool()
    async def to_takeaway(self, context: RunContext_T) -> tuple[Agent, str]:
        """Called when the user wants to update their order."""
        return await self._transfer_to_agent("takeaway", context)


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    basic_agent_knowledge = "התאריך עכשיו הוא 06/06/2025"
    userdata = UserData()
    userdata.agents.update(
        {
            "greeter": Greeter(basic_agent_knowledge),
            "reservation": Reservation(basic_agent_knowledge),
            "takeaway": Takeaway(basic_agent_knowledge),
            "checkout": Checkout(basic_agent_knowledge),
        }
    )
    session = AgentSession[UserData](
        userdata=userdata,
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
            temperature=0.5,
        ),
      
        tts=openai.TTS.with_azure(
            azure_deployment="gpt-4o-mini-tts",
            voice="onyx",
            azure_endpoint=r"https://iofek-mbcpsptu-eastus2.cognitiveservices.azure.com/openai/deployments/gpt-4o-mini-tts/audio/speech?api-version=2025-03-01-preview",
            api_key="4P3LarHA127RY4jDSABYaG5MA6QV4XrBpsJfK1LkjFOEsqcsTsz9JQQJ99BEACHYHv6XJ3w3AAAAACOGME7w",
            api_version="2025-03-01-preview",
        ),
        vad=silero.VAD.load(),
        max_tool_steps=5,
        # to use realtime model, replace the stt, llm, tts and vad with the following
        #   llm=openai.realtime.RealtimeModel.with_azure(
        #     azure_deployment="gpt-4o-realtime-preview",
        #     azure_endpoint=r"https://iofek-mbcpsptu-eastus2.cognitiveservices.azure.com/openai/realtime?api-version=2024-10-01-preview&deployment=gpt-4o-realtime-preview",
        #     api_key="4P3LarHA127RY4jDSABYaG5MA6QV4XrBpsJfK1LkjFOEsqcsTsz9JQQJ99BEACHYHv6XJ3w3AAAAACOGME7w",
        #     api_version="2024-10-01-preview",
        # ),
    )

    await session.start(
        agent=userdata.agents["greeter"],
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # await session.say("שלום, מדברת מערכת זינגר AI ממשרד עורכי הדין זינגר ושות'. אני מתקשרת אליך בעקבות הפנייה שהשארת לנו בנוגע למיצוי זכויות מול ביטוח לאומי. אפשר כמה דקות לדבר? ")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))