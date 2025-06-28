import os
import json
import logging
import aiohttp
from typing import Dict, Optional, Any
from dotenv import load_dotenv
from agents.types import LeadConnectorContact, PhoneStatus
from datetime import datetime, timedelta
import pytz

# Configure logging
logger = logging.getLogger(__name__)
load_dotenv()

# LeadConnector (GoHighLevel) configuration
LEADCONNECTOR_API_KEY = os.getenv('LEADCONNECTOR_API_KEY')
LEADCONNECTOR_LOCATION_ID = os.getenv('LEADCONNECTOR_LOCATION_ID')
LEADCONNECTOR_BASE_URL = "https://rest.gohighlevel.com/v1"

# Israel timezone
ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')


class LeadConnectorService:
    """LeadConnector (GoHighLevel) API service wrapper"""
    
    def __init__(self):
        self.api_key = LEADCONNECTOR_API_KEY
        self.location_id = LEADCONNECTOR_LOCATION_ID
        self.base_url = LEADCONNECTOR_BASE_URL
        
        if not self.api_key:
            logger.warning("LEADCONNECTOR_API_KEY not found in environment variables")
        if not self.location_id:
            logger.warning("LEADCONNECTOR_LOCATION_ID not found in environment variables")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def update_contact(self, contact_id: str, contact_data) -> Dict[str, Any]:
        """
        Update a contact in LeadConnector (GoHighLevel)
        
        Args:
            contact_id: The contact ID to update
            contact_data: Either a LeadConnectorContact object or a dictionary with contact data
            
        Returns:
            Dict containing the API response
        """
        if not self.api_key:
            raise Exception("LEADCONNECTOR_API_KEY not configured")
        
        if not self.location_id:
            raise Exception("LEADCONNECTOR_LOCATION_ID not configured")
        
        # Convert contact data to API format
        api_data = self._prepare_contact_data(contact_data)
        
        url = f"{self.base_url}/contacts/{contact_id}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    url,
                    headers=self._get_headers(),
                    json=api_data
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"Successfully updated contact {contact_id}")
                        logger.info(f"result: {result}")
                        return {
                            "success": True,
                            "data": result,
                            "contact_id": contact_id
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to update contact {contact_id}: {response.status} - {error_text}")
                        logger.error(f"error: {error_text}")
                        return {
                            "success": False,
                            "error": f"API request failed with status {response.status}",
                            "details": error_text,
                            "contact_id": contact_id
                        }
                        
        except Exception as e:
            logger.error(f"Error updating contact {contact_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "contact_id": contact_id
            }
    
    def _prepare_contact_data(self, contact_data) -> Dict[str, Any]:
        """
        Prepare contact data for the LeadConnector API
        
        According to the API docs, the update contact endpoint accepts:
        - Basic fields: email, firstName, lastName, phone, companyName, website, etc.
        - Custom fields: customField[]
        
        Args:
            contact_data: Either a LeadConnectorContact object or a dictionary with contact data
        """
        api_data = {}
        
        # Handle both LeadConnectorContact objects and dictionaries
        if hasattr(contact_data, '__dict__'):
            # It's a LeadConnectorContact object
            contact = contact_data
        else:
            # It's a dictionary
            contact = contact_data
        
        # Basic fields - only include if they exist and are not None/empty
        if hasattr(contact, 'first_name') and contact.first_name:
            api_data["firstName"] = contact.first_name
        elif isinstance(contact, dict) and contact.get('first_name'):
            api_data["firstName"] = contact['first_name']
            
        if hasattr(contact, 'last_name') and contact.last_name:
            api_data["lastName"] = contact.last_name
        elif isinstance(contact, dict) and contact.get('last_name'):
            api_data["lastName"] = contact['last_name']
            
        if hasattr(contact, 'email') and contact.email:
            api_data["email"] = contact.email
        elif isinstance(contact, dict) and contact.get('email'):
            api_data["email"] = contact['email']
            
        if hasattr(contact, 'phone') and contact.phone:
            api_data["phone"] = contact.phone
        elif isinstance(contact, dict) and contact.get('phone'):
            api_data["phone"] = contact['phone']
        
        # Custom fields mapping - only include if they exist and are not None/empty
        custom_fields = []
        
        # Map Hebrew field names to custom fields
        if hasattr(contact, 'is_student_or_registered') and contact.is_student_or_registered:
            custom_fields.append({
                "id": "האם אתה סטודנט או נרשמת ללימודים",
                "value": contact.is_student_or_registered
            })
        elif isinstance(contact, dict) and contact.get('is_student_or_registered'):
            custom_fields.append({
                "id": "האם אתה סטודנט או נרשמת ללימודים",
                "value": contact['is_student_or_registered']
            })
        
        if hasattr(contact, 'diagnoses') and contact.diagnoses:
            custom_fields.append({
                "id": "איזה אבחנות",
                "value": contact.diagnoses
            })
        elif isinstance(contact, dict) and contact.get('diagnoses'):
            custom_fields.append({
                "id": "איזה אבחנות",
                "value": contact['diagnoses']
            })
        
        if hasattr(contact, 'has_diagnoses') and contact.has_diagnoses:
            custom_fields.append({
                "id": "אבחונים",
                "value": contact.has_diagnoses
            })
        elif isinstance(contact, dict) and contact.get('has_diagnoses'):
            custom_fields.append({
                "id": "אבחונים",
                "value": contact['has_diagnoses']
            })
        
        if hasattr(contact, 'medical_problems_description') and contact.medical_problems_description:
            custom_fields.append({
                "id": "תיאור בעיות רפואיות",
                "value": contact.medical_problems_description
            })
        elif isinstance(contact, dict) and contact.get('medical_problems_description'):
            custom_fields.append({
                "id": "תיאור בעיות רפואיות",
                "value": contact['medical_problems_description']
            })
        
        if hasattr(contact, 'disability_percentage') and contact.disability_percentage:
            custom_fields.append({
                "id": "האם נקבעו אחוזי נכות",
                "value": contact.disability_percentage
            })
        elif isinstance(contact, dict) and contact.get('disability_percentage'):
            custom_fields.append({
                "id": "האם נקבעו אחוזי נכות",
                "value": contact['disability_percentage']
            })
        
        if hasattr(contact, 'next_call_time') and contact.next_call_time:
            custom_fields.append({
                "key": "next_call_time",
                "value": contact.next_call_time
            })
        elif isinstance(contact, dict) and contact.get('next_call_time'):
            custom_fields.append({
                "key": "next_call_time",
                "value": contact['next_call_time']
            })
        
        if hasattr(contact, 'phone_status') and contact.phone_status:
            # Convert PhoneStatus enum to string value
            phone_status_value = contact.phone_status.value if hasattr(contact.phone_status, 'value') else str(contact.phone_status)
            custom_fields.append({
                "key": "phone_status",
                "value": phone_status_value
            })
        elif isinstance(contact, dict) and contact.get('phone_status'):
            # Convert PhoneStatus enum to string value
            phone_status = contact['phone_status']
            phone_status_value = phone_status.value if hasattr(phone_status, 'value') else str(phone_status)
            custom_fields.append({
                "key": "phone_status",
                "value": phone_status_value
            })
        
        if hasattr(contact, 'transcript') and contact.transcript:
            custom_fields.append({
                "key": "transcript",
                "value": contact.transcript
            })
        elif isinstance(contact, dict) and contact.get('transcript'):
            custom_fields.append({
                "key": "transcript",
                "value": contact['transcript']
            })
        
        if hasattr(contact, 'meeting_topic') and contact.meeting_topic:
            custom_fields.append({
                "key": "meeting_topic",
                "value": contact.meeting_topic
            })
        elif isinstance(contact, dict) and contact.get('meeting_topic'):
            custom_fields.append({
                "key": "meeting_topic",
                "value": contact['meeting_topic']
            })

        # Add custom fields if any exist
        if custom_fields:
            api_data["customField"] = custom_fields
        
        return api_data
    
    async def get_contact(self, contact_id: str) -> Dict[str, Any]:
        """
        Get a contact from LeadConnector (GoHighLevel)
        
        Args:
            contact_id: The contact ID to retrieve
            
        Returns:
            Dict containing the contact data
        """
        if not self.api_key:
            raise Exception("LEADCONNECTOR_API_KEY not configured")
        
        url = f"{self.base_url}/contacts/{contact_id}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=self._get_headers()
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"Successfully retrieved contact {contact_id}")
                        return {
                            "success": True,
                            "data": result,
                            "contact_id": contact_id
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to get contact {contact_id}: {response.status} - {error_text}")
                        return {
                            "success": False,
                            "error": f"API request failed with status {response.status}",
                            "details": error_text,
                            "contact_id": contact_id
                        }
                        
        except Exception as e:
            logger.error(f"Error getting contact {contact_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "contact_id": contact_id
            }
    
    async def create_contact(self, contact_data: LeadConnectorContact) -> Dict[str, Any]:
        """
        Create a new contact in LeadConnector (GoHighLevel)
        
        Args:
            contact_data: LeadConnectorContact object with contact data
            
        Returns:
            Dict containing the API response with new contact ID
        """
        if not self.api_key:
            raise Exception("LEADCONNECTOR_API_KEY not configured")
        
        if not self.location_id:
            raise Exception("LEADCONNECTOR_LOCATION_ID not configured")
        
        # Convert contact data to API format
        api_data = self._prepare_contact_data(contact_data)
        
        # Add location ID for contact creation
        api_data["locationId"] = self.location_id
        
        url = f"{self.base_url}/contacts/"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=self._get_headers(),
                    json=api_data
                ) as response:
                    
                    if response.status == 201:
                        result = await response.json()
                        logger.info(f"Successfully created contact")
                        logger.info(f"result: {result}")
                        return {
                            "success": True,
                            "data": result,
                            "contact_id": result.get("id")
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to create contact: {response.status} - {error_text}")
                        logger.error(f"error: {error_text}")
                        return {
                            "success": False,
                            "error": f"API request failed with status {response.status}",
                            "details": error_text
                        }
                        
        except Exception as e:
            logger.error(f"Error creating contact: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Global instance
leadconnector_service = LeadConnectorService()


# Convenience functions for backward compatibility
async def update_leadconnector_contact(contact_id: str, contact_data) -> Dict[str, Any]:
    """Update a contact in LeadConnector"""
    return await leadconnector_service.update_contact(contact_id, contact_data)

async def get_leadconnector_contact(contact_id: str) -> Dict[str, Any]:
    """Get a contact from LeadConnector"""
    return await leadconnector_service.get_contact(contact_id)

async def create_leadconnector_contact(contact_data: LeadConnectorContact) -> Dict[str, Any]:
    """Create a new contact in LeadConnector"""
    return await leadconnector_service.create_contact(contact_data)

async def get_transcript(contact_id: str) -> Dict[str, Any]:
    """
    Get the transcript from a contact's custom field
    
    Args:
        contact_id: The contact ID to retrieve the transcript from
        
    Returns:
        Dict containing the transcript data or error information
    """
    if not contact_id:
        return {
            "success": False,
            "error": "Contact ID is required"
        }
    
    try:
        # Get the full contact data
        contact_result = await get_leadconnector_contact(contact_id)
        
        if not contact_result.get("success"):
            return {
                "success": False,
                "error": f"Failed to retrieve contact: {contact_result.get('error', 'Unknown error')}",
                "contact_id": contact_id
            }
        
        contact_data = contact_result.get("data", {})
        contact = contact_data.get("contact", {})
        custom_fields = contact.get("customField", [])
        
        # Find the transcript field with the specific ID
        transcript_field = None
        for field in custom_fields:
            if field.get("id") == "o1cxgUyX4rbPUkJGLM5f":
                transcript_field = field
                break
        
        if transcript_field:
            transcript_value = transcript_field.get("value", "")
            logger.info(f"Successfully retrieved transcript for contact {contact_id}")
            return {
                "success": True,
                "transcript": transcript_value,
                "contact_id": contact_id
            }
        else:
            logger.warning(f"No transcript field found for contact {contact_id}")
            return {
                "success": False,
                "error": "Transcript field not found, contact_result: " + str(contact_result),
                "contact_id": contact_id
            }
            
    except Exception as e:
        logger.error(f"Error getting transcript for contact {contact_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "contact_id": contact_id
        }

async def append_to_transcript(contact_id: str, new_text: str) -> Dict[str, Any]:
    """
    Append new text to a contact's transcript
    
    Args:
        contact_id: The contact ID to update
        new_text: The text to append to the existing transcript
        
    Returns:
        Dict containing the result of the operation
    """
    if not contact_id:
        return {
            "success": False,
            "error": "Contact ID is required"
        }
    
    if not new_text:
        return {
            "success": False,
            "error": "Text to append is required"
        }
    
    try:
        # Get the current transcript
        transcript_result = await get_transcript(contact_id)
        
        if not transcript_result.get("success"):
            # If transcript doesn't exist, create it with the new text
            current_transcript = ""
        else:
            current_transcript = transcript_result.get("transcript", "")
        
        logger.info(f"transcript_result: {transcript_result}")
        # Append the new text
        updated_transcript = current_transcript + "\n" + new_text if current_transcript else new_text
        
        # Prepare contact data with updated transcript
        # ` contact_data = {
        #         "customField": [
        #             {
        #                 "id": "o1cxgUyX4rbPUkJGLM5f",
        #                 "value": updated_transcript
        #             }
        #         ]
        #     }`
        
        # Update the contact
        update_result = await update_leadconnector_contact(contact_id, {"transcript": updated_transcript})
        
        if update_result.get("success"):
            logger.info(f"Successfully appended to transcript for contact {contact_id}")
            return {
                "success": True,
                "transcript": updated_transcript,
                "contact_id": contact_id,
                "appended_text": new_text
            }
        else:
            logger.error(f"Failed to update transcript for contact {contact_id}: {update_result.get('error')}")
            return {
                "success": False,
                "error": f"Failed to update contact: {update_result.get('error', 'Unknown error')}",
                "contact_id": contact_id
            }
            
    except Exception as e:
        logger.error(f"Error appending to transcript for contact {contact_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "contact_id": contact_id
        }

async def get_and_update_phone_status(contact_id: str) -> Dict[str, Any]:
    """
    Get the phone status from a contact and update it to ERROR if it's empty
    
    Args:
        contact_id: The contact ID to check and update
        
    Returns:
        Dict containing the result of the operation
    """
    if not contact_id:
        return {
            "success": False,
            "error": "Contact ID is required"
        }
    
    try:
        # Get the full contact data
        contact_result = await get_leadconnector_contact(contact_id)
        
        if not contact_result.get("success"):
            return {
                "success": False,
                "error": f"Failed to retrieve contact: {contact_result.get('error', 'Unknown error')}",
                "contact_id": contact_id
            }
        
        contact_data = contact_result.get("data", {})
        custom_fields = contact_data.get("customField", [])
        
        # Find the phone status field
        phone_status_field = None
        for field in custom_fields:
            if field.get("id") == "NXOau172nSZOePU6Yqj6":
                phone_status_field = field
                break
        
        current_phone_status = phone_status_field.get("value", "") if phone_status_field else ""
        
        # Check if phone status is empty or None
        if not current_phone_status or current_phone_status.strip() == "":
            # Update phone status to ERROR
            from agents.types import PhoneStatus

            
            update_result = await update_leadconnector_contact(contact_id, {"phone_status": PhoneStatus.ERROR.value})
            
            if update_result.get("success"):
                logger.info(f"Successfully updated phone status to ERROR for contact {contact_id}")
                return {
                    "success": True,
                    "previous_status": current_phone_status,
                    "new_status": PhoneStatus.ERROR.value,
                    "contact_id": contact_id,
                    "was_updated": True
                }
            else:
                logger.error(f"Failed to update phone status for contact {contact_id}: {update_result.get('error')}")
                return {
                    "success": False,
                    "error": f"Failed to update contact: {update_result.get('error', 'Unknown error')}",
                    "contact_id": contact_id,
                    "current_status": current_phone_status
                }
        else:
            logger.info(f"Phone status for contact {contact_id} is not empty: {current_phone_status}")
            return {
                "success": True,
                "current_status": current_phone_status,
                "contact_id": contact_id,
                "was_updated": False
            }
            
    except Exception as e:
        logger.error(f"Error getting and updating phone status for contact {contact_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "contact_id": contact_id
        }

async def update_next_call_time(contact_id: str) -> Dict[str, Any]:
    """
    Update the contact's next call time to the next working day at 10:00.
    
    Working days: Sunday-Thursday
    If today is a working day and before 18:00, set to today 10:00
    If today is a working day and after 18:00, set to next working day 10:00
    If today is Friday or Saturday, set to next Sunday 10:00
    
    Args:
        contact_id: The contact ID to update
        
    Returns:
        Dict containing the result of the operation
    """
    if not contact_id:
        return {
            "success": False,
            "error": "Contact ID is required"
        }
    
    try:
        # Get current time in Israel timezone
        now = datetime.now(ISRAEL_TZ)
        current_hour = now.hour
        
        # Convert to Sunday=0, Monday=1, ..., Thursday=4, Friday=5, Saturday=6
        weekday = (now.weekday() + 1) % 7
        
        # Determine next call time based on current day and time
        if weekday < 5:  # Sunday-Thursday (working day)
            if current_hour < 18:  # Before 18:00
                # Set to today 10:00
                next_call_time = now.replace(hour=10, minute=0, second=0, microsecond=0)
            else:  # After 18:00
                # Set to next working day 10:00
                next_call_time = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
                # Check if next day is weekend and adjust if needed
                next_weekday = (next_call_time.weekday() + 1) % 7
                if next_weekday >= 5:  # Friday or Saturday
                    days_to_add = 7 - next_weekday  # Move to next Sunday
                    next_call_time = next_call_time + timedelta(days=days_to_add)
        else:  # Friday or Saturday (weekend)
            # Set to next Sunday 10:00
            days_to_add = 7 - weekday  # Move to next Sunday
            next_call_time = (now + timedelta(days=days_to_add)).replace(hour=10, minute=0, second=0, microsecond=0)
        
        # Format the date for LeadConnector (ISO format)
        next_call_time_str = next_call_time.date().isoformat()

        
        # Update the contact
        update_result = await update_leadconnector_contact(contact_id, {"next_call_time": next_call_time_str})
        
        if update_result.get("success"):
            logger.info(f"Successfully updated next call time for contact {contact_id} to {next_call_time_str}")
            return {
                "success": True,
                "next_call_time": next_call_time_str,
                "formatted_time": next_call_time.strftime("%Y-%m-%d %H:%M"),
                "day_of_week": next_call_time.strftime("%A"),
                "contact_id": contact_id
            }
        else:
            logger.error(f"Failed to update next call time for contact {contact_id}: {update_result.get('error')}")
            return {
                "success": False,
                "error": f"Failed to update contact: {update_result.get('error', 'Unknown error')}",
                "contact_id": contact_id
            }
            
    except Exception as e:
        logger.error(f"Error updating next call time for contact {contact_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "contact_id": contact_id
        }

async def get_contacts_for_today_calls() -> Dict[str, Any]:
    """
    Get all contacts with next_call_time set to today and phone_status of 
    "Not available to talk" or "Not Answered"
    
    Returns:
        Dict containing the list of contacts that need to be called today
    """
    if not LEADCONNECTOR_API_KEY:
        return {
            "success": False,
            "error": "LEADCONNECTOR_API_KEY not configured"
        }
    
    if not LEADCONNECTOR_LOCATION_ID:
        return {
            "success": False,
            "error": "LEADCONNECTOR_LOCATION_ID not configured"
        }
    
    try:
        # Get current date in Israel timezone for comparison
        today = datetime.now(ISRAEL_TZ).date()
        today_str = today.strftime("%Y-%m-%d")
        
        # Get first 100 contacts from the location
        url = f"{LEADCONNECTOR_BASE_URL}/contacts/"
        params = {
            "locationId": LEADCONNECTOR_LOCATION_ID,
            "limit": 100  # Get only first 100 contacts
        }
        
        contacts_to_call = []
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=leadconnector_service._get_headers(),
                params=params
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    contacts = result.get("contacts", [])
                    
                    logger.info(f"Retrieved {len(contacts)} contacts from LeadConnector")
                    
                    # Process contacts to find those for today's calls
                    for contact in contacts:
                        contact_id = contact.get("id")
                        custom_fields = contact.get("customField", [])
                        
                        # Extract next_call_time and phone_status from custom fields
                        next_call_time = None
                        phone_status = None
                        
                        for field in custom_fields:
                            if field.get("id") == "UPfEjxeXxSh98wlx5oV8":
                                next_call_time = field.get("value")
                            elif field.get("id") == "NXOau172nSZOePU6Yqj6":
                                phone_status = field.get("value")
                        # Check if contact meets criteria
                        if next_call_time and phone_status:
                            try:
                                # Parse the next_call_time - handle different formats
                                if isinstance(next_call_time, int):
                                    # Unix timestamp in milliseconds
                                    call_time = datetime.fromtimestamp(next_call_time / 1000, tz=ISRAEL_TZ)
                                elif isinstance(next_call_time, str):
                                    # String format - try ISO format first
                                    if 'T' in next_call_time or 'Z' in next_call_time:
                                        call_time = datetime.fromisoformat(next_call_time.replace('Z', '+00:00'))
                                        # Convert to Israel timezone for comparison
                                        call_time = call_time.astimezone(ISRAEL_TZ)
                                    else:
                                        # Try date format like "2025-06-28"
                                        call_time = datetime.strptime(next_call_time, "%Y-%m-%d")
                                        call_time = ISRAEL_TZ.localize(call_time)
                                else:
                                    logger.warning(f"Unexpected next_call_time format for contact {contact_id}: {type(next_call_time)}")
                                    continue
                                
                                call_date = call_time.date()
                                
                                # Check if next_call_time is today
                                if call_date == today and phone_status in [PhoneStatus.NOT_AVAILABLE_TO_TALK.value, PhoneStatus.NOT_ANSWERED.value, PhoneStatus.NEW_LEAD.value]:
                                        contact_info = {
                                            "contact_id": contact_id,
                                            "first_name": contact.get("firstName", ""),
                                            "last_name": contact.get("lastName", ""),
                                            "phone": contact.get("phone", ""),
                                            "email": contact.get("email", ""),
                                            "next_call_time": next_call_time,
                                            "phone_status": phone_status,
                                            "call_time_formatted": call_time.strftime("%Y-%m-%d %H:%M")
                                        }
                                        contacts_to_call.append(contact_info)
                                        logger.info(f"Found contact {contact_id} for today's call: {contact_info['first_name']} {contact_info['last_name']} - {phone_status}")
                                        
                            except Exception as e:
                                logger.warning(f"Error parsing next_call_time for contact {contact_id}: {e}")
                                continue
                    
                    logger.info(f"Found {len(contacts_to_call)} contacts to call today")
                    return {
                        "success": True,
                        "contacts": contacts_to_call,
                        "count": len(contacts_to_call),
                        "date": today_str,
                        "total_contacts_processed": len(contacts)
                    }
                    
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get contacts: {response.status} - {error_text}")
                    return {
                        "success": False,
                        "error": f"API request failed with status {response.status}",
                        "details": error_text
                    }
                    
    except Exception as e:
        logger.error(f"Error getting contacts for today's calls: {e}")
        return {
            "success": False,
            "error": str(e)
        }
    
    