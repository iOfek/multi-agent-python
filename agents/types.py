from dataclasses import dataclass, field
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