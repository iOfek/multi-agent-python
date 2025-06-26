import os
import random
from livekit import api
from livekit.agents import JobContext, WorkerOptions
from livekit.agents.voice import AgentSession
from livekit.plugins import openai, silero, noise_cancellation

# LiveKit configuration
LIVEKIT_URL = os.getenv('LIVEKIT_URL')
LIVEKIT_API_KEY = os.getenv('LIVEKIT_API_KEY')
LIVEKIT_API_SECRET = os.getenv('LIVEKIT_API_SECRET')

def get_livekit_api():
    """Get or create LiveKit API instance"""
    lkapi = api.LiveKitAPI(
        url=LIVEKIT_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET
    )
    return lkapi

async def create_agent_dispatch(phone_number: str):
    """Create a LiveKit agent dispatch for outbound calls"""
    livekit_api = get_livekit_api()
    if livekit_api:
        try:
            await livekit_api.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(
                    agent_name="my-telephony-agent", 
                    room=f"outbound-{''.join(str(random.randint(0, 9)) for _ in range(10))}",
                    metadata=f'{{"phone_number": "{phone_number}"}}'
                )
            )
            return True
        except Exception as e:
            print(f"Error creating agent dispatch: {e}")
            return False
        finally:
            await livekit_api.aclose()
    else:
        print("LiveKit API not configured")
        return False

async def add_phone_to_trunk(phone_number: str):
    """
    Add a phone number to the SIP inbound trunk's allowed numbers
    """
    livekit_api = get_livekit_api()
    print(livekit_api)
    
    try:
        rules = await livekit_api.sip.list_sip_inbound_trunk(
            api.ListSIPInboundTrunkRequest()
        )
        print(f"Raw rules object: {type(rules)}")
        print(f"Rules content: {rules}")

        # find the trunk with the id ST_QVWyiWtMs2Mu
        org_trunk = next((trunk for trunk in rules.items if trunk.sip_trunk_id == os.getenv("SIP_INBOUND_TRUNK_ID")), None)
        if org_trunk:
            if phone_number not in org_trunk.allowed_numbers:
                org_trunk.allowed_numbers.append(phone_number)
            else:
                print(f"Phone number {phone_number} already in allowed numbers")
                return org_trunk
        else:
            print(f"Trunk with id {os.getenv('SIP_INBOUND_TRUNK_ID')} not found")
            return {
                "status": "error",
                "message": "Trunk not found"
            }
        
        trunk = await livekit_api.sip.update_sip_inbound_trunk(
            trunk_id = os.getenv("SIP_INBOUND_TRUNK_ID"),
            trunk = org_trunk
        )
        # print(f"Successfully updated trunk {trunk}")        

        
        return trunk
        
    except Exception as e:
        print(f"Error in add_phone_to_trunk: {e}")
        return None
    finally:
        if livekit_api:
            await livekit_api.aclose()

async def remove_phone_from_trunk(phone_number: str):
    """
    Remove a phone number from the SIP inbound trunk's allowed numbers
    """
    livekit_api = get_livekit_api()
    print(livekit_api)
    
    try:
        rules = await livekit_api.sip.list_sip_inbound_trunk(
            api.ListSIPInboundTrunkRequest()
        )
        print(f"Raw rules object: {type(rules)}")
        print(f"Rules content: {rules}")

        # find the trunk with the id ST_QVWyiWtMs2Mu
        org_trunk = next((trunk for trunk in rules.items if trunk.sip_trunk_id == os.getenv("SIP_INBOUND_TRUNK_ID","ST_QVWyiWtMs2Mu")), None)
        if org_trunk:
            if phone_number in org_trunk.allowed_numbers:
                org_trunk.allowed_numbers.remove(phone_number)
                print(f"Trunk: {org_trunk}")
            else:
                print(f"Phone number {phone_number} not found in allowed numbers")
                return None
        else:
            print(f"Trunk with id {os.getenv('SIP_INBOUND_TRUNK_ID')} not found")
            return None
        
        trunk = await livekit_api.sip.update_sip_inbound_trunk(
            trunk_id = os.getenv("SIP_INBOUND_TRUNK_ID"),
            trunk = org_trunk
        )
        print(f"Successfully updated trunk {trunk}")        

        return trunk
        
    except Exception as e:
        print(f"Error in remove_phone_from_trunk: {e}")
        return None
    finally:
        if livekit_api:
            await livekit_api.aclose()

async def get_rooms():
    """Get all LiveKit rooms"""
    livekit_api = get_livekit_api()
    try:
        rooms = await livekit_api.room.list_rooms(api.ListRoomsRequest()).rooms
        return rooms
    except Exception as e:
        print(f"Error getting rooms: {e}")
        return []
    finally:
        if livekit_api:
            await livekit_api.aclose()

async def update_room_metadata(room_name: str, metadata: str):
    """Update room metadata"""
    livekit_api = get_livekit_api()
    try:
        await livekit_api.room.update_room_metadata(
            api.UpdateRoomMetadataRequest(room=room_name, metadata=metadata)
        )
        return True
    except Exception as e:
        print(f"Error updating room metadata: {e}")
        return False
    finally:
        if livekit_api:
            await livekit_api.aclose()

async def find_and_update_room_by_phone(phone_number: str, metadata: str):
    """Find a room by phone number and update its metadata"""
    rooms = await get_rooms()
    room = next((room for room in rooms if phone_number in room.name), None)
    if room:
        return await update_room_metadata(room.name, metadata)
    else:
        print('room not found')
        return False 