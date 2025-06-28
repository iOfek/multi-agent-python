from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Annotated, Optional, List
import yaml

@dataclass
class UserData:
    # Basic client information
    name: Optional[str] = None
    age: Optional[int] = None
    is_student: Optional[bool] = None
    student_details: Optional[str] = None
    
    # Employment information
    is_employed: Optional[bool] = None
    employment_duration: Optional[str] = None
    monthly_income: Optional[float] = None
    
    # Medical condition information
    medical_condition: Optional[str] = None
    diagnosis_date: Optional[str] = None
    medications: List[str] = field(default_factory=list)
    treatment_duration: Optional[str] = None
    
    # Eligibility flags
    meets_income_threshold: Optional[bool] = None
    has_continuous_employment: Optional[bool] = None
    has_medical_documentation: Optional[bool] = None

    # Agent information
    agents: dict[str, 'Agent'] = field(default_factory=dict)
    prev_agent: Optional['Agent'] = None

    def summarize(self) -> str:
        data = {
            "name": self.name or "unknown",
            "age": self.age or "unknown",
            "is_student": self.is_student or False,
            "student_details": self.student_details or "unknown",
            "is_employed": self.is_employed or False,
            "employment_duration": self.employment_duration or "unknown",
            "monthly_income": self.monthly_income or "unknown",
            "medical_condition": self.medical_condition or "unknown",
            "diagnosis_date": self.diagnosis_date or "unknown",
            "medications": self.medications or "unknown",
            "treatment_duration": self.treatment_duration or "unknown",
            "meets_income_threshold": self.meets_income_threshold or False,
            "has_continuous_employment": self.has_continuous_employment or False,
            "has_medical_documentation": self.has_medical_documentation or False,
        }
        # summarize in yaml performs better than json
        return yaml.dump(data)


@dataclass
class PhoneStatus(Enum):
    """Enum for different phone call statuses"""
    ANSWERED = "Answered"
    NOT_ANSWERED = "Not Answered"
    NOT_AVAILABLE_TO_TALK = "Not available to talk"
    ESCALATED_TO_HUMAN = "Escalated to human"
    ERROR = "Error"
    NOT_ELIGIBLE_SET_APPOINTMENT = "Not Eligible set Appointment"
    NOT_ELIGIBLE_NO_APPOINTMENT = "Not Eligible no appointment"
    ELIGIBLE_NO_APPOINTMENT = "Eligible no appointment"
    ELIGIBLE_SET_APPOINTMENT = "Eligible set appointment"
    NEW_LEAD = "New lead"

@dataclass
class LeadConnectorContact:
    """Contact data structure from LeadConnector CRM system"""
    # Basic contact information
    contact_id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    
    # Contact metadata
    tags: Optional[str] = None
    country: Optional[str] = None
    date_created: Optional[str] = None
    
    # Eligibility and qualification fields
    is_student_or_registered: Optional[str] = None  # "האם אתה סטודנט או נרשמת ללימודים"
    diagnoses: Optional[str] = None  # "איזה אבחנות"
    has_diagnoses: Optional[str] = None  # "אבחונים"
    medical_problems_description: Optional[str] = None  # "תיאור בעיות רפואיות"
    disability_percentage: Optional[str] = None  # "האם נקבעו אחוזי נכות"
    
    # Call management fields
    next_call_time: Optional[datetime] = None  # "Next Call Time" format: 2020-10-29T09:31:30.255Z
    phone_status: Optional[PhoneStatus] = None  # "Phone Status"
    transcript: Optional[str] = None  # "Transcript"
    meeting_topic: Optional[str] = None  # "Meeting Topic"
    
    def __init__(self, **kwargs):
        """Initialize the dataclass, ignoring any fields not defined in the class"""
        # Get all the field names defined in this dataclass
        import dataclasses
        field_names = {field.name for field in dataclasses.fields(self.__class__)}
        
        # Filter kwargs to only include defined fields
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in field_names}
        
        # Initialize the dataclass with filtered kwargs
        for field_name, value in filtered_kwargs.items():
            setattr(self, field_name, value)


@dataclass
class ConfirmationTracking:
    """Type for WhatsApp confirmation tracking data"""
    phone_number: str
    date: Optional[str] = None
    time: Optional[str] = None
    status: Optional[str] = None  # "pending", "approved", "declined"
    sent_at: Optional[str] = None
    answered_at: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary format for storage"""
        return {
            "date": self.date,
            "time": self.time,
            "status": self.status,
            "sent_at": self.sent_at,
            "answered_at": self.answered_at
        }
    
    @classmethod
    def from_dict(cls, phone_number: str, data: dict) -> 'ConfirmationTracking':
        """Create from dictionary format"""
        return cls(
            phone_number=phone_number,
            date=data.get("date"),
            time=data.get("time"),
            status=data.get("status"),
            sent_at=data.get("sent_at"),
            answered_at=data.get("answered_at")
        ) 