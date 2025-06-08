from datetime import datetime
import logging
from dotenv import load_dotenv

from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import AgentSession
from livekit.agents.voice.room_io import RoomInputOptions
from livekit.plugins import openai, silero

from agents import (
    UserData,
    Greeter,
    Reservation,
    Takeaway,
    Checkout,
)
from agents.adhd_specialist import AdhdSpecialist
from agents.eligibility import Eligibility
from agents.fibro_specialist import FibroSpecialist
from agents.medical import Medical
from agents.meeting_setup import MeetingSetup
from agents.migraine_specialist import MigraineSpecialist
from agents.process_explanation import ProcessExplanation
from agents.psyche_specialist import PsycheSpecialist
from agents.specialist import Specialist

logger = logging.getLogger("restaurant-example")
logger.setLevel(logging.INFO)

load_dotenv()

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
            "medical": Medical(basic_agent_knowledge),
            "eligibility": Eligibility(basic_agent_knowledge),
            # "specialist": Specialist(basic_agent_knowledge),
            "adhd_specialist": AdhdSpecialist(basic_agent_knowledge),
            "psyche_specialist": PsycheSpecialist(basic_agent_knowledge),
            "migraine_specialist": MigraineSpecialist(basic_agent_knowledge),
            "fibro_specialist": FibroSpecialist(basic_agent_knowledge),
            "meeting_setup": MeetingSetup(basic_agent_knowledge),
            "process_explanation": ProcessExplanation(basic_agent_knowledge),
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
    )

    await session.start(
        agent=userdata.agents["greeter"],
        # agent=userdata.agents["eligibility"],
        # agent=userdata.agents["medical"],
        room=ctx.room,
        room_input_options=RoomInputOptions(),
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))