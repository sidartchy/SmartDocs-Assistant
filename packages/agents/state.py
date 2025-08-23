from __future__ import annotations

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class BookingStep(Enum):
    COLLECTING_NAME = "collecting_name"
    COLLECTING_PHONE = "collecting_phone"
    COLLECTING_EMAIL = "collecting_email"
    COLLECTING_DATE = "collecting_date"
    CONFIRMING = "confirming"
    COMPLETED = "completed"


@dataclass
class BookingState:
    """Represents the current state of a booking conversation."""
    step: BookingStep
    collected: Dict[str, Any]
    required_fields: List[str]
    chat_id: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step.value,
            "collected": self.collected,
            "required_fields": self.required_fields,
            "chat_id": self.chat_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BookingState":
        return cls(
            step=BookingStep(data["step"]),
            collected=data["collected"],
            required_fields=data["required_fields"],
            chat_id=data["chat_id"]
        )


class BookingStateManager:
    """Manages booking conversation state and slot-filling logic."""
    
    def __init__(self):
        self.states: Dict[str, BookingState] = {}
    
    def get_state(self, chat_id: str) -> Optional[BookingState]:
        """Get the current booking state for a chat."""
        return self.states.get(chat_id)
    
    def create_state(self, chat_id: str) -> BookingState:
        """Create a new booking state."""
        state = BookingState(
            step=BookingStep.COLLECTING_NAME,
            collected={},
            required_fields=["name", "phone", "email", "date_time"],
            chat_id=chat_id
        )
        self.states[chat_id] = state
        return state
    
    def update_state(self, chat_id: str, **updates) -> BookingState:
        """Update the booking state."""
        if chat_id not in self.states:
            raise ValueError(f"No booking state found for chat_id: {chat_id}")
        
        state = self.states[chat_id]
        for key, value in updates.items():
            if hasattr(state, key):
                setattr(state, key, value)
        
        return state
    
    def add_collected_info(self, chat_id: str, field: str, value: Any) -> BookingState:
        """Add collected information to the state."""
        state = self.get_state(chat_id)
        if not state:
            raise ValueError(f"No booking state found for chat_id: {chat_id}")
        
        state.collected[field] = value
        return state
    
    def get_next_required_field(self, state: BookingState) -> Optional[str]:
        """Get the next required field that needs to be collected."""
        for field in state.required_fields:
            if field not in state.collected:
                return field
        return None
    
    def is_complete(self, state: BookingState) -> bool:
        """Check if all required fields have been collected."""
        return all(field in state.collected for field in state.required_fields)
    
    def clear_state(self, chat_id: str) -> None:
        """Clear the booking state for a chat."""
        if chat_id in self.states:
            del self.states[chat_id]


# Global instance
booking_state_manager = BookingStateManager()
