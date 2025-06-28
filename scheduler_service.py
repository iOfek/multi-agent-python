import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
import pytz

from agents.types import LeadConnectorContact
from leadconnector_service import get_contacts_for_today_calls
from livekit_service import add_phone_to_trunk, create_agent_dispatch
from utils import is_within_working_hours

# Configure logging
logger = logging.getLogger(__name__)

# Israel timezone
ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')


class CallScheduler:
    """Scheduler for making outbound calls to contacts with next_call_time of today"""
    
    def __init__(self):
        self.is_running = False
        self.scheduler_task = None
        self.stop_event = asyncio.Event()
    
    def start(self):
        """Start the scheduler"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        try:
            # Create and start the scheduler task
            self.stop_event.clear()
            self.scheduler_task = asyncio.create_task(self._scheduler_loop())
            self.is_running = True
            logger.info("Call scheduler started successfully")
            logger.info("Scheduled jobs:")
            logger.info("  - Test calls at 10:00")
            logger.info("  - Afternoon calls at 14:00")
            logger.info("  - Evening calls at 18:00")
                
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            self.is_running = False
            raise
    
    def stop(self):
        """Stop the scheduler"""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return
        
        try:
            self.stop_event.set()
            if self.scheduler_task:
                self.scheduler_task.cancel()
            self.is_running = False
            logger.info("Call scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
    
    async def _scheduler_loop(self):
        """Main scheduler loop that runs continuously"""
        logger.info("🔄 Scheduler loop started")
        
        while not self.stop_event.is_set():
            try:
                now = datetime.now(ISRAEL_TZ)
                current_hour = now.hour
                current_minute = now.minute
                
                # Check if it's a working day (Sunday-Thursday)
                weekday = (now.weekday() + 1) % 7  # Convert to Sunday=0, Monday=1, ..., Thursday=4, Friday=5, Saturday=6
                
                # Only run on working days (Sunday-Thursday)
                if weekday <= 4:  # Sunday=0, Monday=1, Tuesday=2, Wednesday=3, Thursday=4
                    # Check if it's time to run (10:00, 14:00, or 18:00)
                    if current_hour in [10, 14, 18] and current_minute == 0:
                        logger.info(f"🕐 Scheduled time reached: {current_hour}:{current_minute:02d}")
                        await self.process_today_calls()
                else:
                    # Log that we're skipping due to weekend
                    if current_hour in [10, 14, 18] and current_minute == 0:
                        logger.info(f"📅 Weekend detected ({now.strftime('%A')}) - skipping scheduled calls")
                
                # Wait for 1 minute before next check
                await asyncio.wait_for(self.stop_event.wait(), timeout=60)
                
            except asyncio.TimeoutError:
                # This is expected - continue the loop
                continue
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                # Wait a bit before retrying
                await asyncio.sleep(60)
        
        logger.info("🔄 Scheduler loop stopped")
    
    async def process_today_calls(self):
        """
        Process calls for contacts with next_call_time of today.
        This function mimics the logic from the clickup-webhook endpoint.
        """
        logger.info("🕐 Starting scheduled call processing...")
        
        try:
            # TODO: Add after testing
            # # Check if within working hours
            # if not is_within_working_hours():
            #     logger.info("⏰ Outside working hours - skipping scheduled calls")
            #     return
            
            # Get contacts for today's calls
            contacts_result = await get_contacts_for_today_calls()
            
            if not contacts_result.get("success"):
                logger.error(f"Failed to get contacts for today's calls: {contacts_result.get('error')}")
                return
            
            contacts = contacts_result.get("contacts", [])
            logger.info(f"📞 Found {len(contacts)} contacts to call today")
            
            if not contacts:
                logger.info("No contacts to call today")
                return
            
            # Process each contact
            successful_calls = 0
            failed_calls = 0
           
            for contact in contacts:
                try:
                    contact_id = contact.get("contact_id")
                    phone_number = contact.get("phone")
                    first_name = contact.get("first_name", "")
                    last_name = contact.get("last_name", "")
                    
                    logger.info(f"📞 Processing call for {first_name} {last_name} ({phone_number})")
                    
                    if not phone_number or not contact_id:
                        logger.warning(f"Missing phone number or contact ID for contact {contact_id}")
                        failed_calls += 1
                        continue
                    
                    # Create LeadConnectorContact object for the call
                    contact_data = LeadConnectorContact(
                        contact_id=contact_id,
                        phone=phone_number,
                        first_name=first_name,
                        last_name=last_name,
                        email=contact.get("email", ""),
                        is_student_or_registered=contact.get("is_student_or_registered"),
                        diagnoses=contact.get("diagnoses"),
                        has_diagnoses=contact.get("has_diagnoses"),
                        medical_problems_description=contact.get("medical_problems_description"),
                        disability_percentage=contact.get("disability_percentage"),
                        next_call_time=contact.get("next_call_time"),
                        phone_status=contact.get("phone_status"),
                        transcript=contact.get("transcript"),
                        meeting_topic=contact.get("meeting_topic")
                    )
                    
                    # Add phone to LiveKit trunk
                    trunk_result = await add_phone_to_trunk(phone_number)
                    if not trunk_result:
                        logger.error(f"Failed to add phone {phone_number} to trunk")
                        failed_calls += 1
                        continue
                    
                    # Create agent dispatch (make the call)
                    dispatch_result = await create_agent_dispatch(contact_data)
                    if dispatch_result:
                        logger.info(f"✅ Successfully created agent dispatch for {phone_number}")
                        successful_calls += 1
                    else:
                        logger.error(f"Failed to create agent dispatch for {phone_number}")
                        failed_calls += 1
                    
                    # Add a small delay between calls to avoid overwhelming the system
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error processing call for contact {contact.get('contact_id')}: {e}")
                    failed_calls += 1
            
            logger.info(f"📊 Call processing completed: {successful_calls} successful, {failed_calls} failed")
            
        except Exception as e:
            logger.error(f"Error in process_today_calls: {e}")
    
    async def manual_trigger(self):
        """
        Manually trigger the call processing (for testing or manual execution)
        """
        logger.info("🔧 Manually triggering call processing...")
        if not is_within_working_hours():
            logger.info("⏰ Outside working hours - skipping manual call processing")
            return
        
        # Check if it's a working day (Sunday-Thursday)
        now = datetime.now(ISRAEL_TZ)
        weekday = (now.weekday() + 1) % 7  # Convert to Sunday=0, Monday=1, ..., Thursday=4, Friday=5, Saturday=6
        
        if weekday > 4:  # Friday (5) or Saturday (6)
            logger.info(f"📅 Outside working days: {now.strftime('%A')} (weekday {weekday}) - skipping manual call processing")
            return
        
        await self.process_today_calls()


# Global scheduler instance
call_scheduler = CallScheduler()


# Convenience functions
def start_scheduler():
    """Start the call scheduler"""
    call_scheduler.start()

def stop_scheduler():
    """Stop the call scheduler"""
    call_scheduler.stop()

async def trigger_manual_call_processing():
    """Manually trigger call processing"""
    await call_scheduler.manual_trigger() 