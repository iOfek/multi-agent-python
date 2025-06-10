from datetime import datetime
import logging
from dotenv import load_dotenv

from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import AgentSession
from livekit.agents.voice.room_io import RoomInputOptions
from livekit.plugins import openai, silero, google

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
from agents.other_specialist import OtherSpecialist
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
            "adhd_specialist": AdhdSpecialist(basic_agent_knowledge),
            "psyche_specialist": PsycheSpecialist(basic_agent_knowledge),
            "migraine_specialist": MigraineSpecialist(basic_agent_knowledge),
            "fibro_specialist": FibroSpecialist(basic_agent_knowledge),
            "other_specialist": OtherSpecialist(basic_agent_knowledge),
            "meeting_setup": MeetingSetup(basic_agent_knowledge),
            "process_explanation": ProcessExplanation(basic_agent_knowledge),
        }
    )
    session = AgentSession[UserData](
        userdata=userdata,
        # OPENAI STT LLM TTS
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
            temperature=0.6,
        ),
        # llm=openai.LLM.with_azure(
        #     azure_deployment="gpt-4.1-nano",
        #     azure_endpoint=r"https://iofek-mbcpsptu-eastus2.cognitiveservices.azure.com/openai/deployments/gpt-4.1-nano/chat/completions?api-version=2025-01-01-preview",
        #     api_key="4P3LarHA127RY4jDSABYaG5MA6QV4XrBpsJfK1LkjFOEsqcsTsz9JQQJ99BEACHYHv6XJ3w3AAAAACOGME7w",
        #     api_version="2025-01-01-preview",
        #     temperature=0.5,
        # ),
  
        tts=openai.TTS.with_azure(
            instructions="cheerful soothing voice",
            azure_deployment="gpt-4o-mini-tts",
            voice="onyx",
            azure_endpoint=r"https://iofek-mbcpsptu-eastus2.cognitiveservices.azure.com/openai/deployments/gpt-4o-mini-tts/audio/speech?api-version=2025-03-01-preview",
            api_key="4P3LarHA127RY4jDSABYaG5MA6QV4XrBpsJfK1LkjFOEsqcsTsz9JQQJ99BEACHYHv6XJ3w3AAAAACOGME7w",
            api_version="2025-03-01-preview",
        ),

        #  OPENAI REALTIME
        # llm=openai.realtime.RealtimeModel.with_azure(
        #     azure_deployment="gpt-4o-realtime-preview",
        #     azure_endpoint="https://iofek-mbcpsptu-eastus2.cognitiveservices.azure.com/openai/realtime?api-version=2024-10-01-preview&deployment=gpt-4o-realtime-preview",
        #     api_key="4P3LarHA127RY4jDSABYaG5MA6QV4XrBpsJfK1LkjFOEsqcsTsz9JQQJ99BEACHYHv6XJ3w3AAAAACOGME7w",
        #     api_version="2024-10-01-preview",
        # ),

        # GOOGLE REALTIME
        # llm=google.beta.realtime.RealtimeModel(
        #     model="gemini-2.5-flash-exp-native-audio-thinking-dialog",
        #     voice="Leda",
        #     temperature=0.8,
        #     api_key="AIzaSyDI7n55EhLyKkOB5NqmGKJI4kwwP9jRbh0",
        # ),

        # GOOGLE STT LLM TTS
        # stt=google.STT(
        #     languages="iw-IL",
        #     credentials_file="gen-lang-client-0666698830-fbeb9dfc2cd2.json",
        #     punctuate=False,
        #     model="default",
        #     location="asia-southeast1",

        # ),
        # stt=openai.STT.with_azure(
        #     azure_deployment="gpt-4o-transcribe",
        #     azure_endpoint=r"https://iofek-mbcpsptu-eastus2.cognitiveservices.azure.com/openai/deployments/gpt-4o-transcribe/audio/transcriptions?api-version=2025-03-01-preview",
        #     api_key="4P3LarHA127RY4jDSABYaG5MA6QV4XrBpsJfK1LkjFOEsqcsTsz9JQQJ99BEACHYHv6XJ3w3AAAAACOGME7w",
        #     api_version="2025-03-01-preview",
        #     language="he",
        # ),

        # llm=google.LLM(

        #     model="gemini-2.5-flash-preview-05-20",
        #     api_key="AIzaSyDI7n55EhLyKkOB5NqmGKJI4kwwP9jRbh0",
        # ),
        # llm=openai.LLM.with_azure(
        #     azure_deployment="gpt-4.1",
        #     azure_endpoint=r"https://iofek-mbcpsptu-eastus2.cognitiveservices.azure.com/openai/deployments/gpt-4.1/chat/completions?api-version=2025-01-01-preview",
        #     api_key="4P3LarHA127RY4jDSABYaG5MA6QV4XrBpsJfK1LkjFOEsqcsTsz9JQQJ99BEACHYHv6XJ3w3AAAAACOGME7w",
        #     api_version="2025-01-01-preview",
        #     temperature=0.5,
        # ),
               #  OPENAI REALTIME
        # llm=openai.realtime.RealtimeModel.with_azure(
        #     azure_deployment="gpt-4o-realtime-preview",
        #     azure_endpoint="https://iofek-mbcpsptu-eastus2.cognitiveservices.azure.com/openai/realtime?api-version=2024-10-01-preview&deployment=gpt-4o-realtime-preview",
        #     api_key="4P3LarHA127RY4jDSABYaG5MA6QV4XrBpsJfK1LkjFOEsqcsTsz9JQQJ99BEACHYHv6XJ3w3AAAAACOGME7w",
        #     api_version="2024-10-01-preview",
        # ),

        #  tts=openai.TTS.with_azure(
        #     azure_deployment="gpt-4o-mini-tts",
        #     voice="onyx",
        #     azure_endpoint=r"https://iofek-mbcpsptu-eastus2.cognitiveservices.azure.com/openai/deployments/gpt-4o-mini-tts/audio/speech?api-version=2025-03-01-preview",
        #     api_key="4P3LarHA127RY4jDSABYaG5MA6QV4XrBpsJfK1LkjFOEsqcsTsz9JQQJ99BEACHYHv6XJ3w3AAAAACOGME7w",
        #     api_version="2025-03-01-preview",
        # ),
        # tts=google.TTS(
        #     # language="he-IL",
        #     credentials_file="gen-lang-client-0666698830-fbeb9dfc2cd2.json",
        #     voice_name="he-IL-Standard-A"
        # ),

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
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint,agent_name="greeter"))