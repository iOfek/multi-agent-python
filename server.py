import random
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import PlainTextResponse
from pyngrok import ngrok
import os
import hmac
import hashlib
import base64
import json
import asyncio
from datetime import datetime, timedelta
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

# In-memory storage for WhatsApp confirmations
# In production, use a proper database like Redis or PostgreSQL
whatsapp_confirmations = {}

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

def extract_phone_from_whatsapp_number(whatsapp_number: str) -> str:
    """
    Extract phone number from WhatsApp number format (e.g., 'whatsapp:+972527001042' -> '+972527001042')
    """
    if whatsapp_number.startswith('whatsapp:'):
        return whatsapp_number[9:]  # Remove 'whatsapp:' prefix
    return whatsapp_number

def store_confirmation(phone_number: str, meeting_details: str = ""):
    """
    Store confirmation for a phone number
    """
    whatsapp_confirmations[phone_number] = {
        "confirmed": True,
        "confirmed_at": datetime.now().isoformat(),
        "meeting_details": meeting_details
    }
    print(f"✅ Stored confirmation for {phone_number}: {whatsapp_confirmations[phone_number]}")

def get_confirmation_status(phone_number: str) -> dict:
    """
    Get confirmation status for a phone number
    """
    confirmation = whatsapp_confirmations.get(phone_number)
    if confirmation:
        return {
            "confirmed": confirmation["confirmed"],
            "confirmed_at": confirmation["confirmed_at"],
            "meeting_details": confirmation.get("meeting_details", "")
        }
    return {"confirmed": False, "confirmed_at": None, "meeting_details": ""}

def set_confirmation_status(phone_number: str, status: str):
    """
    Set confirmation status for a phone number
    """
    whatsapp_confirmations[phone_number] = {
        "confirmed": status,
        "confirmed_at": datetime.now().isoformat(),
        "meeting_details": ""
    }
    print(f"✅ Set confirmation status for {phone_number}: {whatsapp_confirmations[phone_number]}")

def clear_confirmation(phone_number: str):
    """
    Clear confirmation for a phone number (useful for testing)
    """
    if phone_number in whatsapp_confirmations:
        del whatsapp_confirmations[phone_number]
        print(f"🗑️ Cleared confirmation for {phone_number}")

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

@app.get('/whatsapp-confirmation-status/{phone_number}')
async def get_whatsapp_confirmation_status(phone_number: str):
    """
    Check WhatsApp confirmation status for a phone number
    """
    status = get_confirmation_status(phone_number)
    return {
        "phone_number": phone_number,
        "status": status
    }

@app.get('/whatsapp-confirmation-status/{phone_number}/{status}')
async def update_whatsapp_confirmation_status(phone_number: str, status: str):
    """
    Check WhatsApp confirmation status for a phone number
    """
    status = set_confirmation_status(phone_number, status)
    return {
        "phone_number": phone_number,
        "status": status
    }

@app.get('/clear-whatsapp-confirmation/{phone_number}')
async def clear_whatsapp_confirmation(phone_number: str):
    """
    Clear WhatsApp confirmation for a phone number (for testing)
    """
    clear_confirmation(phone_number)
    return {"status": "success", "message": f"Confirmation cleared for {phone_number}"}

@app.get('/whatsapp-confirmations')
async def list_whatsapp_confirmations():
    """
    List all WhatsApp confirmations (for debugging)
    """
    return {
        "confirmations": whatsapp_confirmations,
        "count": len(whatsapp_confirmations)
    }

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
    

@app.get('/livekit-get-rooms')
async def livekit_get_rooms(request: Request):
    """Health check endpoint for monitoring"""
    livekit_api = get_livekit_api()
    rooms = await livekit_api.room.list_rooms(api.ListRoomsRequest()).rooms
    print('rooms', rooms)
    room = next((room for room in rooms if "+972527001042" in room.name), None)
    print('room', room)
    if room:
        await livekit_api.room.update_room_metadata(api.UpdateRoomMetadataRequest(room=room.name, metadata=f'{{"confirmed": "true"}}'))
        print('room updated')
    else:
        print('room not found')
    await livekit_api.aclose()
    return {"status": "success"}
    
    


@app.post("/whatsapp-webhook")
async def whatsapp_webhook(request: Request):
    # Log the raw request body first
    body = await request.body()
    print("🔍 Raw request body:", body.decode('utf-8'))
    
    # Parse form data
    form_data = await request.form()
    print("🔍 Form data:", dict(form_data))
    
    # Extract fields with fallbacks
    From = form_data.get('From', '')
    Body = form_data.get('Body', '')
    ButtonText = form_data.get('ButtonText', '')
    ButtonPayload = form_data.get('ButtonPayload', '')
    InteractiveType = form_data.get('InteractiveType', '')
    InteractiveButtonReply = form_data.get('InteractiveButtonReply', '')
    InteractiveListReply = form_data.get('InteractiveListReply', '')
    
    # Also check for other possible field names
    MessageType = form_data.get('MessageType', '')
    Type = form_data.get('Type', '')
    
    print("📞 From:", From)
    print("💬 Body:", Body)
    print("🔘 ButtonPayload:", ButtonPayload)
    print("🔘 ButtonText:", ButtonText)
    print("🔘 InteractiveType:", InteractiveType)
    print("🔘 InteractiveButtonReply:", InteractiveButtonReply)
    print("🔘 InteractiveListReply:", InteractiveListReply)
    print("🔘 MessageType:", MessageType)
    print("🔘 Type:", Type)

    # Extract phone number from WhatsApp number
    phone_number = extract_phone_from_whatsapp_number(From)
    print(f"📱 Extracted phone number: {phone_number}")

    # Check for button interactions - try multiple approaches
    button_payload = None
    
    # Method 1: Direct button payload
    if ButtonPayload:
        button_payload = ButtonPayload
        print("✅ Found button payload via ButtonPayload field")
    
    # Method 2: Interactive button reply
    elif InteractiveType == "button_reply" and InteractiveButtonReply:
        button_payload = InteractiveButtonReply
        print("✅ Found button payload via InteractiveButtonReply field")
    
    # Method 3: Check if it's an interactive message
    elif InteractiveType or Type == "interactive":
        # Try to parse the Body as JSON if it contains interactive data
        try:
            import json
            body_data = json.loads(Body)
            if 'button_reply' in body_data:
                button_payload = body_data['button_reply'].get('id', '')
                print("✅ Found button payload in JSON body")
        except:
            pass
    
    if button_payload:
        print("✅ Button clicked:", button_payload)
        if button_payload == "CONFIRM_MEETING":
            # Store confirmation for this phone number
            store_confirmation(phone_number, "Meeting confirmed via WhatsApp")
            print("✅ Confirm meeting button clicked - confirmation stored")
            # Add your calendar creation logic here
            pass
        elif button_payload == "DECLINE_MEETING":
            # Handle rejection flow
            print("❌ Decline meeting button clicked")
            pass
    else:
        print("💬 Text reply or no button detected:", Body)

    return PlainTextResponse("OK")

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