from datetime import datetime
from typing import Annotated
from pydantic import Field
from livekit.agents.llm import function_tool
from livekit.agents import get_job_context
from livekit import api

from .types import UserData
from .base_agent import RunContext, Agent

@function_tool()
async def update_name(
    name: Annotated[str, Field(description="The customer's name")],
    context: RunContext,
) -> str:
    """Called when the user provides their name.
    Confirm the spelling with the user before calling the function."""
    userdata = context.userdata
    userdata.name = name
    return f"The name is updated to {name}"

@function_tool()
async def update_phone(
    phone: Annotated[str, Field(description="The customer's phone number")],
    context: RunContext,
) -> str:
    """Called when the user provides their phone number.
    Confirm the spelling with the user before calling the function."""
    userdata = context.userdata
    userdata.customer_phone = phone
    return f"The phone number is updated to {phone}"

@function_tool()
async def to_greeter(context: RunContext) -> Agent:
    """Called when user asks any unrelated questions or requests
    any other services not in your job description."""
    curr_agent = context.session.current_agent
    return await curr_agent._transfer_to_agent("greeter", context)

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

@function_tool()
async def end_call(context: RunContext) -> Agent:
    """נקרא כאשר סיימנו לאסוף את כל הפרטים הנדרשים מהלקוח"""
    # let the agent finish speaking
    current_speech = context.session.current_speech
    if current_speech:
        await current_speech.wait_for_playout()
    await hangup_call() 


@function_tool()
async def convert_datetime_to_speech(
    date_str: Annotated[str, Field(description="The date in format DD.MM.YYYY")],
    time_str: Annotated[str, Field(description="The time in 24-hour format HH:MM")],
    context: RunContext,
) -> str:
    """
    Converts a date and time into natural spoken Hebrew, like:
    'עשרים ושלושה באוגוסט בשעה חמש'
    """

    # Hebrew mappings
    day_map = {
        1: "ראשון", 2: "שני", 3: "שלישי", 4: "רביעי", 5: "חמישי",
        6: "שישי", 7: "שביעי", 8: "שמיני", 9: "תשיעי", 10: "עשירי",
        11: "אחד עשר", 12: "שניים עשר", 13: "שלושה עשר", 14: "ארבעה עשר",
        15: "חמישה עשר", 16: "שישה עשר", 17: "שבעה עשר", 18: "שמונה עשר",
        19: "תשעה עשר", 20: "עשרים", 21: "עשרים ואחד", 22: "עשרים ושניים",
        23: "עשרים ושלושה", 24: "עשרים וארבעה", 25: "עשרים וחמישה",
        26: "עשרים ושישה", 27: "עשרים ושבעה", 28: "עשרים ושמונה",
        29: "עשרים ותשעה", 30: "שלושים", 31: "שלושים ואחד"
    }

    month_map = {
        1: "ינואר", 2: "פברואר", 3: "מרץ", 4: "אפריל", 5: "מאי", 6: "יוני",
        7: "יולי", 8: "אוגוסט", 9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר"
    }

    hour_map = {
        0: "שתים עשרה", 1: "אחת", 2: "שתיים", 3: "שלוש", 4: "ארבע", 5: "חמש",
        6: "שש", 7: "שבע", 8: "שמונה", 9: "תשע", 10: "עשר", 11: "אחת עשרה",
        12: "שתים עשרה", 13: "אחת", 14: "שתיים", 15: "שלוש", 16: "ארבע",
        17: "חמש", 18: "שש", 19: "שבע", 20: "שמונה", 21: "תשע", 22: "עשר",
        23: "אחת עשרה"
    }

    # Parse date and time
    dt = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
    day = day_map[dt.day]
    month = month_map[dt.month]
    hour = hour_map[dt.hour]

    return f"{day} ב{month} בשעה {hour}"