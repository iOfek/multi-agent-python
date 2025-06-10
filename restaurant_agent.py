from datetime import datetime
import logging
from dotenv import load_dotenv

from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import AgentSession
from livekit.agents.voice.room_io import RoomInputOptions
from livekit.plugins import openai, silero, google
from openai.types.beta.realtime.session import TurnDetection, InputAudioNoiseReduction
# from livekit.plugins.turn_detector.multilingual import MultilingualModel

# from livekit.plugins.openai.realtime import MultilingualModel

from agents import (
    UserData,
    Greeter,
    Reservation,
    Takeaway,
    Checkout,
)

from agents.specialist import Specialist

logger = logging.getLogger("restaurant-example")
logger.setLevel(logging.INFO)

load_dotenv()

async def entrypoint(ctx: JobContext):
    await ctx.connect()

    basic_agent_knowledge = "התאריך עכשיו הוא 06/06/2025"
    userdata = UserData()
    # userdata.agents.update(
    #     {
    #         "greeter": Greeter(basic_agent_knowledge),
    #         "reservation": Reservation(basic_agent_knowledge),
    #         "takeaway": Takeaway(basic_agent_knowledge),
    #         "checkout": Checkout(basic_agent_knowledge),
    #         "medical": Medical(basic_agent_knowledge),
    #         "eligibility": Eligibility(basic_agent_knowledge),
    #         "adhd_specialist": AdhdSpecialist(basic_agent_knowledge),
    #         "psyche_specialist": PsycheSpecialist(basic_agent_knowledge),
    #         "migraine_specialist": MigraineSpecialist(basic_agent_knowledge),
    #         "fibro_specialist": FibroSpecialist(basic_agent_knowledge),
    #         "other_specialist": OtherSpecialist(basic_agent_knowledge),
    #         "meeting_setup": MeetingSetup(basic_agent_knowledge),
    #         "process_explanation": ProcessExplanation(basic_agent_knowledge),
    #     }
    # )
    session = AgentSession[UserData](
        userdata=userdata,
        # OPENAI REALTIME
        # llm= openai.realtime.RealtimeModel(
        #     model="gpt-4o-realtime-preview-2025-06-03",
        # ),
        # allow_interruptions=True,
        # turn_detection=MultilingualModel(),

        #  AZUREOPENAI REALTIME
        llm=openai.realtime.RealtimeModel.with_azure(
            azure_deployment="gpt-4o-realtime-preview",
            voice="alloy",
            azure_endpoint="https://iofek-mbcpsptu-eastus2.cognitiveservices.azure.com/openai/realtime?api-version=2024-10-01-preview&deployment=gpt-4o-realtime-preview",
            api_key="4P3LarHA127RY4jDSABYaG5MA6QV4XrBpsJfK1LkjFOEsqcsTsz9JQQJ99BEACHYHv6XJ3w3AAAAACOGME7w",
            api_version="2024-10-01-preview",
            temperature=0.6,
            turn_detection=TurnDetection(
                type="semantic_vad",
                # threshold=0.5,
                # silence_duration_ms=500,
                # prefix_padding_ms=300,
                eagerness="low",
            ),
            input_audio_noise_reduction=InputAudioNoiseReduction(
                type="near_field",
            )
        ),

        # GOOGLE REALTIME
        # llm=google.beta.realtime.RealtimeModel(
        #     model="gemini-2.5-flash-exp-native-audio-thinking-dialog",
        #     voice="Leda",
        #     temperature=0.8,
        #     api_key="AIzaSyDI7n55EhLyKkOB5NqmGKJI4kwwP9jRbh0",
        # ),


        vad=silero.VAD.load(),
        max_tool_steps=5,
    )

    await session.start(
        agent=Greeter(basic_agent_knowledge),
        # agent=userdata.agents["eligibility"],
        # agent=userdata.agents["medical"],
        room=ctx.room,
        room_input_options=RoomInputOptions(),
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint,agent_name="greeter"))