import os
import json
import logging
import aiohttp
from typing import Dict, Optional, Any
from dotenv import load_dotenv
from agents.types import LeadConnectorContact

# Configure logging
logger = logging.getLogger(__name__)
load_dotenv()

# LeadConnector (GoHighLevel) configuration
LEADCONNECTOR_API_KEY = os.getenv('LEADCONNECTOR_API_KEY')
LEADCONNECTOR_LOCATION_ID = os.getenv('LEADCONNECTOR_LOCATION_ID')
LEADCONNECTOR_BASE_URL = "https://rest.gohighlevel.com/v1"


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
        custom_fields = contact_data.get("customField", [])
        
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
                "error": "Transcript field not found",
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
        
        # Append the new text
        updated_transcript = current_transcript + "\n" + new_text if current_transcript else new_text
        
        # Prepare contact data with updated transcript
        contact_data = {
            "customField": [
                {
                    "id": "o1cxgUyX4rbPUkJGLM5f",
                    "value": updated_transcript
                }
            ]
        }
        
        # Update the contact
        update_result = await update_leadconnector_contact(contact_id, contact_data)
        
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
    
    