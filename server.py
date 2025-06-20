import random
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from pyngrok import ngrok
import os
import hmac
import hashlib
import base64
import json
import asyncio
from livekit import api
from livekit.agents import JobContext, WorkerOptions
from livekit.agents.voice import AgentSession
from livekit.plugins import openai, silero, noise_cancellation
import logging

app = FastAPI()
# CORS(app)  # Disabled CORS for now

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

# ClickUp webhook secret - you should set this as an environment variable
CLICKUP_WEBHOOK_SECRET = os.getenv('CLICKUP_WEBHOOK_SECRET', 'your-webhook-secret-here')

# Static ngrok domain - set this as an environment variable
STATIC_NGROK_DOMAIN = os.getenv('STATIC_NGROK_DOMAIN', 'new-destined-ray.ngrok-free.app')

# LiveKit configuration
LIVEKIT_URL = os.getenv('LIVEKIT_URL')
LIVEKIT_API_KEY = os.getenv('LIVEKIT_API_KEY')
LIVEKIT_API_SECRET = os.getenv('LIVEKIT_API_SECRET')

# Twilio configuration for outbound calls
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_SIP_DOMAIN = os.getenv('TWILIO_SIP_DOMAIN')

# Initialize LiveKit API
lkapi = None

def get_livekit_api():
    """Get or create LiveKit API instance"""
    lkapi = api.LiveKitAPI(
        url=LIVEKIT_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET
    )
    return lkapi

def verify_clickup_signature(request_body, signature):
    """
    Verify the ClickUp webhook signature to ensure the request is authentic
    """
    if not CLICKUP_WEBHOOK_SECRET or CLICKUP_WEBHOOK_SECRET == 'your-webhook-secret-here':
        print("Warning: Using default webhook secret. Set CLICKUP_WEBHOOK_SECRET environment variable for production.")
        return True  # Allow requests if no secret is configured
    
    expected_signature = base64.b64encode(
        hmac.new(
            CLICKUP_WEBHOOK_SECRET.encode('utf-8'),
            request_body,
            hashlib.sha256
        ).digest()
    ).decode('utf-8')
    
    return hmac.compare_digest(signature, expected_signature)

@app.post('/clickup-webhook')
async def clickup_webhook(request: Request):
    try:
        # Verify the request signature - DISABLED FOR NOW
        # signature = request.headers.get('X-ClickUp-Signature')
        # if signature:
        #     if not verify_clickup_signature(request.get_data(), signature):
        #         return jsonify({"status": "error", "message": "Invalid signature"}), 401
        
        data = await request.json()
        print("Received ClickUp Webhook Data:")
        # Print with Hebrew support - ensure_ascii=False preserves Hebrew characters
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
        # Also print with RTL marker for better Hebrew display
        print("\n--- RTL Format ---")
        rtl_json = json.dumps(data, indent=2, ensure_ascii=False)
        # Add RTL marker at the beginning
        print("\u202B" + rtl_json)

        # Process the data based on the 'event' field
        event = data.get('event')
        
        if True:  # if event == 'taskCreated':
            task_id = data.get('task_id')
            print(f"New task created: {task_id}")
            
            # Extract phone number from task data
            phone_number = extract_phone_number_from_task(data)
            
            if phone_number:
                if await add_phone_to_trunk(phone_number):
                    # Make outbound call asynchronously - now we can use await directly!
                    livekit_api = get_livekit_api()
                    if livekit_api:
                        await livekit_api.agent_dispatch.create_dispatch(
                            api.CreateAgentDispatchRequest(
                                agent_name="my-telephony-agent", 
                                room=f"outbound-{''.join(str(random.randint(0, 9)) for _ in range(10))}",
                                metadata=f'{{"phone_number": "{phone_number}"}}'
                            )
                        )
                    else:
                        print("LiveKit API not configured")
                        raise HTTPException(status_code=400, detail="LiveKit API not configured")
                else:
                    print("Failed to add phone number to trunk")
                    raise HTTPException(status_code=400, detail="Failed to add phone number to trunk")
            else:
                print("No phone number found in task data")
                raise HTTPException(status_code=400, detail="No phone number found in task data")

        return {"status": "success"}
    except Exception as e:
        print(f"Error processing webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid request data")

def extract_phone_number_from_task(task_data: dict) -> str:
    """
    Extract phone number from ClickUp task data
    Customize this function based on your task structure
    """
    print(task_data.keys())
    phone_number = task_data.get('phone', None)
    return phone_number 

    # print(phone_number)
    # if phone_number:
    #     # check if phone number is valid
    #     if  phone_number.startswith('0'):
    #         phone_number = '+972' + phone_number[1:]
    #     if not phone_number.startswith('+972'):
    #         return phone_number 
    # return None

@app.get('/health')
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "service": "clickup-webhook-server"}

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
        None
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

@app.get('/livekit-remove-phone')
async def livekit_remove_phone(request: Request):
    """Health check endpoint for monitoring"""
    if await remove_phone_from_trunk("+972527001042"):
        return {"status": "success"}
    else:
        return {"status": "error"}

@app.get('/livekit-add-phone')
async def livekit_add_phone(request: Request):
    """Health check endpoint for monitoring"""
    if await add_phone_to_trunk("+972505536704"):
        return {"status": "success"}
    else:
        return {"status": "error"}

if __name__ == '__main__':
    import uvicorn
    # Set up ngrok to expose the local server
    port = 5000
    
    # Start ngrok tunnel with static domain
    public_url = ngrok.connect(port, domain=STATIC_NGROK_DOMAIN)
    print(f"Ngrok tunnel established at: {public_url}")
    print(f"Your webhook URL is: {public_url}/clickup-webhook")
    print(f"Health check URL: {public_url}/health")
    
    # Run the FastAPI app with uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)