import random
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request, HTTPException, Response
from fastapi.responses import PlainTextResponse, RedirectResponse
from pyngrok import ngrok,conf
from pyngrok.exception import PyngrokNgrokError
import os
import hmac
import hashlib
import base64
import json
import asyncio
from datetime import datetime, timedelta
import logging
import pickle
from twilio.rest import Client
from twilio.http.async_http_client import AsyncTwilioHttpClient
from agents.types import ConfirmationTracking, LeadConnectorContact, PhoneStatus
import pytz
from contextlib import asynccontextmanager

# Import utility functions
from utils import is_within_working_hours

# Import calendar functionality from the new module
from calendar_service import (
    calendar_service, 
    calendar_oauth, 
    CALENDAR_USER_ID,
    get_calendar_service,
    get_available_slots,
    load_calendar_token,
    save_calendar_token
)

# Import LiveKit functionality from the new module
from livekit_service import (
    create_agent_dispatch,
    add_phone_to_trunk,
    remove_phone_from_trunk,
    get_rooms,
    update_room_metadata
)

# Import LeadConnector functionality
from leadconnector_service import (
    leadconnector_service,
    update_leadconnector_contact,
    get_leadconnector_contact,
    create_leadconnector_contact,
    update_next_call_time,
    get_contacts_for_today_calls
)

# Import scheduler functionality
from scheduler_service import start_scheduler, stop_scheduler, trigger_manual_call_processing

# Global scheduler instance
scheduler_started = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI startup and shutdown"""
    # Startup
    global scheduler_started
    if not scheduler_started:
        try:
            # Start the call scheduler
            print("🕐 Starting call scheduler...")
            start_scheduler()
            print("✅ Call scheduler started successfully")
            scheduler_started = True
        except Exception as e:
            print(f"❌ Failed to start scheduler: {e}")
            print("⚠️ Server will continue without scheduler")
    
    yield
    
    # Shutdown
    try:
        stop_scheduler()
        print("✅ Call scheduler stopped")
    except Exception as e:
        print(f"⚠️ Error stopping scheduler: {e}")

app = FastAPI(lifespan=lifespan)
# CORS(app)  # Disabled CORS for now

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

# Israel timezone
ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')

# ---------------------------------------------------------------------------
# TWILIO CLIENT
# ---------------------------------------------------------------------------
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

# Initialize client as None, will be set up when needed
client = None

def get_twilio_client():
    """Get or create the Twilio client with async support"""
    global client
    if client is None:
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            print("⚠️ Warning: Twilio credentials not found. WhatsApp functionality will not work.")
            print("Please set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment variables.")
            return None
        else:
            # Use async HTTP client for async operations
            async_http_client = AsyncTwilioHttpClient()
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, http_client=async_http_client)
            print("✅ Twilio async client initialized successfully")
    return client

# ClickUp webhook secret - you should set this as an environment variable
CLICKUP_WEBHOOK_SECRET = os.getenv('CLICKUP_WEBHOOK_SECRET', 'your-webhook-secret-here')

# Static ngrok domain - set this as an environment variable
STATIC_NGROK_DOMAIN = os.getenv('STATIC_NGROK_DOMAIN', 'new-destined-ray.ngrok-free.app')

# Twilio configuration for outbound calls
TWILIO_SIP_DOMAIN = os.getenv('TWILIO_SIP_DOMAIN')

# In-memory storage for confirmation tracking
# In production, use a proper database like Redis or PostgreSQL
confirmation_tracking = {}

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
        

        # Create LeadConnectorContact from the webhook data
        contact_data = LeadConnectorContact(**data)
        print(f"Contact data: {contact_data}")
        
        # Extract phone number from the LeadConnectorContact
        phone_number = contact_data.phone
        contact_id = contact_data.contact_id
        
        if phone_number and contact_id:
            # Add phone to LiveKit trunk
            if await add_phone_to_trunk(phone_number):
                # Check if within working hours before creating agent dispatch
                if is_within_working_hours():
                    # Make outbound call using the new LiveKit service
                    if await create_agent_dispatch(contact_data):
                        print(f"✅ Successfully created agent dispatch for {phone_number}")
                    else:
                        print("Failed to create agent dispatch")
                        raise HTTPException(status_code=400, detail="Failed to create agent dispatch")
                else:
                    print(f"⏰ Outside working hours - agent dispatch skipped for {phone_number}")
                    await update_next_call_time(contact_id)
                    await update_leadconnector_contact(contact_id, {"phone_status": PhoneStatus.NEW_LEAD.value})
                    # Return success but log that dispatch was skipped
                    return {"status": "success", "message": "Agent dispatch skipped - outside working hours"}
            else:
                print("Failed to add phone number to trunk")
                raise HTTPException(status_code=400, detail="Failed to add phone number to trunk")
        else:
            print("No phone number found in LeadConnectorContact")
            raise HTTPException(status_code=400, detail="No phone number found in LeadConnectorContact")

        return {"status": "success"}
    except Exception as e:
        print(f"Error processing webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid request data")

@app.post('/leadconnector/manual_call')
async def manual_call(request: Request):
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
        

        # Create LeadConnectorContact from the webhook data
        contact_data = LeadConnectorContact(**data)
        print(f"Contact data: {contact_data}")
        
        # Extract phone number from the LeadConnectorContact
        phone_number = contact_data.phone
        contact_id = contact_data.contact_id
        
        if phone_number and contact_id:
            # Add phone to LiveKit trunk
            if await add_phone_to_trunk(phone_number):
                    # Make outbound call using the new LiveKit service
                    if await create_agent_dispatch(contact_data):
                        print(f"✅ Successfully created agent dispatch for {phone_number}")
                    else:
                        print("Failed to create agent dispatch")
                        raise HTTPException(status_code=400, detail="Failed to create agent dispatch")
            else:
                print("Failed to add phone number to trunk")
                raise HTTPException(status_code=400, detail="Failed to add phone number to trunk")
        else:
            print("No phone number found in LeadConnectorContact")
            raise HTTPException(status_code=400, detail="No phone number found in LeadConnectorContact")

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


@app.get('/oauth2callback')
async def oauth2callback(code: str = None, state: str = None, error: str = None):
    """
    OAuth2 callback endpoint for Google Calendar authorization
    """
    if error:
        return {"error": f"OAuth error: {error}"}
    
    try:
        result = calendar_oauth.handle_callback(code)
        return result
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return {"error": f"Failed to complete OAuth: {str(e)}"}

@app.get('/calendar/authorize')
async def authorize_calendar():
    """
    Start OAuth2 flow for calendar authorization
    """
    try:
        authorization_url = calendar_oauth.get_authorization_url()
        return RedirectResponse(url=authorization_url)
    except Exception as e:
        logger.error(f"Authorization error: {e}")
        raise HTTPException(status_code=500, detail=f"Authorization failed: {str(e)}")

@app.get('/calendar/availability')
async def get_calendar_availability(preference: str):
    """
    Get available calendar slots
    """
    try:
        # Get available slots
        slots = calendar_service.get_available_slots(preference)
        
        return {
            "user_id": CALENDAR_USER_ID,
            "preference": preference,
            "available_slots": slots,
            "count": len(slots)
        }
        
    except Exception as e:
        logger.error(f"Calendar availability error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get availability: {str(e)}")


@app.get('/livekit-remove-phone')
async def livekit_remove_phone(request: Request):
    """Remove phone number from LiveKit trunk"""
    if await remove_phone_from_trunk("+972527001042"):
        return {"status": "success"}
    else:
        return {"status": "error"}

@app.get('/livekit-add-phone')
async def livekit_add_phone(request: Request):
    """Add phone number to LiveKit trunk"""
    if await add_phone_to_trunk("+972505536704"):
        return {"status": "success"}
    else:
        return {"status": "error"}

@app.post('/scheduler/trigger-calls')
async def trigger_scheduled_calls():
    """Manually trigger the scheduled call processing"""
    try:
        await trigger_manual_call_processing()
        return {"status": "success", "message": "Call processing triggered successfully"}
    except Exception as e:
        logger.error(f"Error triggering call processing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger call processing: {str(e)}")

@app.get('/scheduler/status')
async def get_scheduler_status():
    """Get the current status of the scheduler"""
    from scheduler_service import call_scheduler
    now = datetime.now(ISRAEL_TZ)
    
    return {
        "status": "running" if call_scheduler.is_running else "stopped",
        "current_time": now.isoformat(),
        "jobs": [
            {
                "id": "morning_calls",
                "name": "Morning calls at 10:00",
                "next_run": f"{now.date()}T04:13:00+03:00" if now.hour < 10 else f"{(now + timedelta(days=1)).date()}T10:00:00+03:00"
            },
            {
                "id": "afternoon_calls", 
                "name": "Afternoon calls at 14:00",
                "next_run": f"{now.date()}T14:00:00+03:00" if now.hour < 14 else f"{(now + timedelta(days=1)).date()}T14:00:00+03:00"
            },
            {
                "id": "evening_calls",
                "name": "Evening calls at 18:00", 
                "next_run": f"{now.date()}T18:00:00+03:00" if now.hour < 18 else f"{(now + timedelta(days=1)).date()}T18:00:00+03:00"
            }
        ]
    }

@app.post('/scheduler/start')
async def start_scheduler_endpoint():
    """Start the scheduler"""
    try:
        start_scheduler()
        return {"status": "success", "message": "Scheduler started successfully"}
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start scheduler: {str(e)}")

@app.post('/scheduler/stop')
async def stop_scheduler_endpoint():
    """Stop the scheduler"""
    try:
        stop_scheduler()
        return {"status": "success", "message": "Scheduler stopped successfully"}
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop scheduler: {str(e)}")

async def send_whatsapp_confirmation(phone_number: str, date: str, time: str):
    """
    Send confirmation to WhatsApp
    """
    twilio_client = get_twilio_client()
    if twilio_client is None:
        raise Exception("Twilio client not initialized. Please check your TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment variables.")
    
    whatsapp_number = f"whatsapp:{phone_number}"
    message = await twilio_client.messages.create_async(
        from_='whatsapp:+97233763938',
        content_sid='HX582776fc767a4635abebe81969d15ca6',
        content_variables='{"1":"'+date+'","2":"'+time+'"}',
        to=whatsapp_number
    )
    return message

async def send_whatsapp_meeting_link(phone_number: str, meeting_link: str):
    """
    Send confirmation to WhatsApp
    """
    twilio_client = get_twilio_client()
    if twilio_client is None:
        raise Exception("Twilio client not initialized. Please check your TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment variables.")
    
    whatsapp_number = f"whatsapp:{phone_number}"
    message = await twilio_client.messages.create_async(
        from_='whatsapp:+97233763938',
        # content_sid='HX582776fc767a4635abebe81969d15ca6', #DEMO
        content_sid='HXcc8209b59801f087738f4cb809913ada', #DEMO
        content_variables='{"1":"'+meeting_link+'"}',
        to=whatsapp_number
    )
    return message

async def get_confirmation_tracking_status(phone_number: str) -> ConfirmationTracking:
    """
    Get confirmation tracking
    """
    return confirmation_tracking.get(phone_number, {})

async def set_confirmation_tracking(phone_number: str, date: str | None = None, time: str | None = None, status: str | None = None, sent_at: str | None = None, answered_at: str | None = None) -> ConfirmationTracking:
    """
    Set confirmation tracking
    """
    # Get existing tracking data or create new tracking object
    existing_data = confirmation_tracking.get(phone_number, {})
    tracking = ConfirmationTracking.from_dict(phone_number, existing_data)
    
    # Update only the fields that are provided
    if status:
        tracking.status = status
    if sent_at:
        tracking.sent_at = sent_at 
    if answered_at:
        tracking.answered_at = answered_at
    if date:
        tracking.date = date
    if time:
        tracking.time = time

    # Store the updated data
    confirmation_tracking[phone_number] = tracking.to_dict()

    print(f"📱 WhatsApp confirmation tracking set for {phone_number} for date: {date} and time: {time}")
    return tracking

@app.get('/whatsapp/get_confirmation_tracking_status/{phone_number}')
async def get_confirmation_tracking_status_endpoint(phone_number: str):
    """
    Get confirmation tracking status
    """
    # return as json 
    confirmation_status = await get_confirmation_tracking_status(phone_number)
    return {"status": "success", "confirmation_status": confirmation_status.status}

@app.post('/whatsapp/send_confirmation')
async def send_confirmation(request: Request):
    """
    Send confirmation to WhatsApp
    """
    try:
        form_data = await request.form()
        phone_number = form_data.get('phone_number', '')
        date = form_data.get('date', '')
        time = form_data.get('time', '')
        
        print(f"📱 Received confirmation request for {phone_number} on {date} at {time}")
        
        # Validate required fields
        if not phone_number or not date or not time:
            logger.error(f"Missing required fields: phone_number={phone_number}, date={date}, time={time}")
            raise HTTPException(status_code=400, detail="Missing required fields: phone_number, date, time")
        
        # Send WhatsApp confirmation
        try:
            await send_whatsapp_confirmation(phone_number, date, time)
            print(f"✅ WhatsApp confirmation sent successfully to {phone_number}")
        except Exception as e:
            logger.error(f"Failed to send WhatsApp confirmation: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to send WhatsApp confirmation: {str(e)}")
        
        # Set confirmation tracking
        try:
            await set_confirmation_tracking(phone_number, date, time, "pending", datetime.now(ISRAEL_TZ).isoformat(), None)
            print(f"✅ Confirmation tracking set for {phone_number}")
        except Exception as e:
            logger.error(f"Failed to set confirmation tracking: {e}")
            # Don't fail the entire request if tracking fails
            print(f"⚠️ Warning: Failed to set confirmation tracking: {e}")

        print(f"📱 WhatsApp confirmation sent to {phone_number} for date: {date} and time: {time}")
        return {"status": "success"}
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in send_confirmation: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")



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
    button_payload = form_data.get('ButtonPayload', '')
    
    
    print("📞 From:", From)
    print("💬 Body:", Body)


    # Extract phone number from WhatsApp number
    phone_number = extract_phone_from_whatsapp_number(From)
    print(f"📱 Extracted phone number: {phone_number}")


    if button_payload:
        print("✅ Button clicked:", button_payload)
        if button_payload == "confirmation1234":
            # Store confirmation for this phone number
            print("✅ Confirm meeting button clicked - confirmation stored")
            
         
                
            # Book the calendar slot
            try:
                confirmation_tracking = await get_confirmation_tracking_status(phone_number)
                # Create a slot ID from date and time (you may need to adjust this based on your calendar service)
                print(f"📱 Confirmation tracking: {confirmation_tracking}")
                booking_result = calendar_service.book_slot(confirmation_tracking.date, confirmation_tracking.time, phone_number)
                print(f"✅ Calendar booking result: {booking_result}")
                
                # Extract meet link from the booking result
                meet_link = booking_result.get('meet_link')
                if not meet_link:
                    raise Exception("No meet link generated from calendar booking")
                
                await send_whatsapp_meeting_link(phone_number, meet_link)

                await set_confirmation_tracking(phone_number, status="approved", answered_at=datetime.now(ISRAEL_TZ).isoformat())
                # Update confirmation tracking status
                print(f"📱 Confirmation tracking: {confirmation_tracking}")



            except Exception as e:
                print(f"❌ Error booking calendar: {e}")
                # Continue anyway - the confirmation is still valid
            
        elif button_payload == "cancellation1234":
            # Handle rejection flow
            print("❌ Decline meeting button clicked")
            await set_confirmation_tracking(phone_number, status="declined", answered_at=datetime.now(ISRAEL_TZ).isoformat())
            
    else:
        print("💬 Text reply or no button detected:", Body)

    return PlainTextResponse("OK")

if __name__ == '__main__':
    import uvicorn
    import asyncio
    
    # Set up ngrok to expose the local server
    port = 5000
    
    # Start ngrok tunnel with static domain
    conf.get_default().ngrok_path = "C:\\ProgramData\\chocolatey\\bin\\ngrok.exe"  # Use system-installed binary

    try:
        public_url = ngrok.connect(port, domain=STATIC_NGROK_DOMAIN)
        print(f"Ngrok tunnel established at: {public_url}")
        print(f"Your webhook URL is: {public_url}/clickup-webhook")
        print(f"Health check URL: {public_url}/health")
    except PyngrokNgrokError as e:
        if "limited to 1 simultaneous ngrok agent sessions" in str(e):
            print("⚠️ Warning: Another ngrok session is already running")
            print("💡 You can either:")
            print("   1. Stop the other ngrok session and restart")
            print("   2. Use the existing tunnel URL")
            print("   3. Run without ngrok (server will be local only)")
            
            # Try to get existing tunnels
            try:
                tunnels = ngrok.get_ngrok_process().api.get_tunnels()
                if tunnels:
                    existing_url = tunnels[0].public_url
                    print(f"📡 Existing tunnel found: {existing_url}")
                    print(f"Your webhook URL is: {existing_url}/clickup-webhook")
                    print(f"Health check URL: {existing_url}/health")
                else:
                    print("❌ No existing tunnels found")
            except Exception:
                print("❌ Could not retrieve existing tunnels")
            
            print("🚀 Starting server without new ngrok tunnel...")
        else:
            print(f"❌ Ngrok error: {e}")
            print("🚀 Starting server without ngrok tunnel...")
    except Exception as e:
        print(f"❌ Unexpected error with ngrok: {e}")
        print("🚀 Starting server without ngrok tunnel...")
    
    try:
        # Run the FastAPI app with uvicorn
        uvicorn.run(app, host="0.0.0.0", port=port)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
        try:
            stop_scheduler()
            print("✅ Call scheduler stopped")
        except Exception as e:
            print(f"⚠️ Error stopping scheduler: {e}")
        print("👋 Server shutdown complete")
    except Exception as e:
        print(f"❌ Server error: {e}")
        try:
            stop_scheduler()
            print("✅ Call scheduler stopped")
        except Exception as scheduler_error:
            print(f"⚠️ Error stopping scheduler: {scheduler_error}")
        raise