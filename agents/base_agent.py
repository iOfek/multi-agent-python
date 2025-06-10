from datetime import datetime
import logging
from typing import Optional, Dict, Type

from livekit.agents.voice import Agent, RunContext
from livekit.plugins import openai

logger = logging.getLogger("restaurant-example")
logger.setLevel(logging.INFO)

class BaseAgent(Agent):
    async def on_enter(self) -> None:
        agent_name = self.__class__.__name__
        logger.info(f"entering task {agent_name}")

        userdata = self.session.userdata
        self.session.generate_reply(tool_choice="none")

    async def _transfer_to_agent(self, name: str, context: RunContext) -> tuple[Agent, str]:
        userdata = context.userdata
        current_agent = context.session.current_agent
        userdata.prev_agent = current_agent
        basic_agent_knowledge=f"You are {name} agent. Current user data is {userdata.summarize()}"

        # Lazy load agent classes
        agent_classes: Dict[str, Type[BaseAgent]] = {
            "greeter": None,
            "reservation": None,
            "medical": None,
            "eligibility": None,
            "adhd_specialist": None,
            "psyche_specialist": None,
            "migraine_specialist": None,
            "fibro_specialist": None,
            "other_specialist": None,
            "meeting_setup": None,
            "process_explanation": None,
        }

        # Import the specific agent class when needed
        if name == "greeter":
            from agents.greeter import Greeter
            agent_classes["greeter"] = Greeter
        elif name == "reservation":
            from agents.reservation import Reservation
            agent_classes["reservation"] = Reservation
        elif name == "medical":
            from agents.medical import Medical
            agent_classes["medical"] = Medical
        elif name == "eligibility":
            from agents.eligibility import Eligibility
            agent_classes["eligibility"] = Eligibility
        elif name == "adhd_specialist":
            from agents.adhd_specialist import AdhdSpecialist
            agent_classes["adhd_specialist"] = AdhdSpecialist
        elif name == "psyche_specialist":
            from agents.psyche_specialist import PsycheSpecialist
            agent_classes["psyche_specialist"] = PsycheSpecialist
        elif name == "migraine_specialist":
            from agents.migraine_specialist import MigraineSpecialist
            agent_classes["migraine_specialist"] = MigraineSpecialist
        elif name == "fibro_specialist":
            from agents.fibro_specialist import FibroSpecialist
            agent_classes["fibro_specialist"] = FibroSpecialist
        elif name == "other_specialist":
            from agents.other_specialist import OtherSpecialist
            agent_classes["other_specialist"] = OtherSpecialist
        elif name == "meeting_setup":
            from agents.meeting_setup import MeetingSetup
            agent_classes["meeting_setup"] = MeetingSetup
        elif name == "process_explanation":
            from agents.process_explanation import ProcessExplanation
            agent_classes["process_explanation"] = ProcessExplanation

        agent_class = agent_classes[name]
        if agent_class is None:
            raise ValueError(f"Unknown agent type: {name}")

        next_agent = agent_class(basic_agent_knowledge)
        return next_agent, "" 