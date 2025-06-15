from datetime import datetime
import logging
import os
from dotenv import load_dotenv

from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import AgentSession
from livekit.agents.voice.room_io import RoomInputOptions
from livekit.plugins import openai, silero, google, noise_cancellation
from livekit import api

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
from agents.utils import load_prompt

logger = logging.getLogger("restaurant-example")
logger.setLevel(logging.INFO)

load_dotenv()

async def entrypoint(ctx: JobContext):

    # lkapi = api.LiveKitAPI()

    # room = await lkapi.room.create_room(api.CreateRoomRequest(
    #     name="my-room",
    #     empty_timeout=10 * 60,
    #     max_participants=20,
    # ))




    await ctx.connect()

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
        llm=openai.LLM.with_azure(
            azure_deployment=os.getenv("AZURE_OPENAI_GPT41_DEPLOYMENT"),
            azure_endpoint=os.getenv("AZURE_OPENAI_GPT41_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_NORTHCENTRALUS_API_KEY"),
            api_version="2025-01-01-preview",
            temperature=0.6,
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
        allow_interruptions=False,
    )

    await session.start(
        agent=Greeter(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVCTelephony(),
        ),
    )

    # await lkapi.aclose()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint,agent_name="greeter"))