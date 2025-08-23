from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BookingRecord(BaseModel):
    booking_id: str = Field(description="Unique identifier for the booking")
    chat_id: str = Field(description="Chat session ID where booking was created")
    name: str = Field(description="Name of the person")
    email: str = Field(description="Email address")
    phone: str = Field(description="Phone number")
    meeting_date: datetime = Field(description="Scheduled meeting date/time")
    meeting_title: str = Field(description="Title of the meeting")
    status: str = Field(description="Booking status (confirmed, cancelled, etc.)")
    created_at: datetime = Field(description="When booking was created")
    updated_at: datetime = Field(description="When booking was last updated")
    calendar_event_id: Optional[str] = Field(description="Calendar event ID if created")
    meeting_link: Optional[str] = Field(description="Video meeting link if available")
    notes: Optional[str] = Field(description="Additional notes")


class PersistenceResult(BaseModel):
    success: bool = Field(description="Whether persistence operation was successful")
    booking_id: Optional[str] = Field(description="Unique identifier for the booking")
    file_path: Optional[str] = Field(description="Path where booking was saved")
    error_message: Optional[str] = Field(description="Error message if operation failed")


def persist_booking(
    chat_id: str,
    name: str,
    email: str,
    phone: str,
    meeting_date: datetime,
    meeting_title: str,
    calendar_event_id: Optional[str] = None,
    meeting_link: Optional[str] = None,
    notes: Optional[str] = None,
) -> PersistenceResult:
    """
    Save booking information to persistent storage.
    
    Args:
        chat_id: Chat session ID where booking was created
        name: Name of the person
        email: Email address
        phone: Phone number
        meeting_date: Scheduled meeting date/time
        meeting_title: Title of the meeting
        calendar_event_id: Optional calendar event ID
        meeting_link: Optional video meeting link
        notes: Optional additional notes
    
    Returns:
        PersistenceResult with success status and booking details
    """
    try:
        # Create bookings directory if it doesn't exist
        bookings_dir = Path("data/bookings")
        bookings_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate booking ID
        booking_id = f"booking_{int(datetime.now().timestamp())}_{hash(email)}"
        
        # Create booking record
        booking = BookingRecord(
            booking_id=booking_id,
            chat_id=chat_id,
            name=name,
            email=email,
            phone=phone,
            meeting_date=meeting_date,
            meeting_title=meeting_title,
            status="confirmed",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            calendar_event_id=calendar_event_id,
            meeting_link=meeting_link,
            notes=notes
        )
        
        # Save to JSON file
        file_path = bookings_dir / f"{booking_id}.json"
        with open(file_path, "w") as f:
            json.dump(booking.model_dump(), f, indent=2, default=str)
        
        return PersistenceResult(
            success=True,
            booking_id=booking_id,
            file_path=str(file_path),
            error_message=None
        )
        
    except Exception as e:
        return PersistenceResult(
            success=False,
            booking_id=None,
            file_path=None,
            error_message=str(e)
        )


def get_booking(booking_id: str) -> Optional[BookingRecord]:
    """
    Retrieve a booking by ID.
    
    Args:
        booking_id: Unique identifier for the booking
    
    Returns:
        BookingRecord if found, None otherwise
    """
    try:
        bookings_dir = Path("data/bookings")
        file_path = bookings_dir / f"{booking_id}.json"
        
        if not file_path.exists():
            return None
        
        with open(file_path, "r") as f:
            data = json.load(f)
        
        # Convert string dates back to datetime
        data["meeting_date"] = datetime.fromisoformat(data["meeting_date"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        
        return BookingRecord(**data)
        
    except Exception:
        return None


def get_bookings_by_email(email: str) -> List[BookingRecord]:
    """
    Get all bookings for a specific email address.
    
    Args:
        email: Email address to search for
    
    Returns:
        List of BookingRecord objects
    """
    bookings = []
    try:
        bookings_dir = Path("data/bookings")
        
        if not bookings_dir.exists():
            return bookings
        
        for file_path in bookings_dir.glob("*.json"):
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                
                if data.get("email") == email:
                    # Convert string dates back to datetime
                    data["meeting_date"] = datetime.fromisoformat(data["meeting_date"])
                    data["created_at"] = datetime.fromisoformat(data["created_at"])
                    data["updated_at"] = datetime.fromisoformat(data["updated_at"])
                    
                    bookings.append(BookingRecord(**data))
                    
            except Exception:
                continue
        
        # Sort by meeting date (most recent first)
        bookings.sort(key=lambda x: x.meeting_date, reverse=True)
        
    except Exception:
        pass
    
    return bookings


def update_booking_status(booking_id: str, status: str, notes: Optional[str] = None) -> PersistenceResult:
    """
    Update the status of a booking.
    
    Args:
        booking_id: Unique identifier for the booking
        status: New status (confirmed, cancelled, completed, etc.)
        notes: Optional additional notes
    
    Returns:
        PersistenceResult with success status
    """
    try:
        booking = get_booking(booking_id)
        if not booking:
            return PersistenceResult(
                success=False,
                booking_id=booking_id,
                file_path=None,
                error_message="Booking not found"
            )
        
        # Update booking
        booking.status = status
        booking.updated_at = datetime.now()
        if notes:
            booking.notes = notes
        
        # Save updated booking
        bookings_dir = Path("data/bookings")
        file_path = bookings_dir / f"{booking_id}.json"
        
        with open(file_path, "w") as f:
            json.dump(booking.model_dump(), f, indent=2, default=str)
        
        return PersistenceResult(
            success=True,
            booking_id=booking_id,
            file_path=str(file_path),
            error_message=None
        )
        
    except Exception as e:
        return PersistenceResult(
            success=False,
            booking_id=booking_id,
            file_path=None,
            error_message=str(e)
        )


def get_all_bookings() -> List[Dict[str, Any]]:
    """
    Get all bookings from the storage.
    
    Returns:
        List of booking dictionaries
    """
    bookings = []
    try:
        bookings_dir = Path("data/bookings")
        
        if not bookings_dir.exists():
            return bookings
        
        for file_path in bookings_dir.glob("*.json"):
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                bookings.append(data)
            except Exception:
                continue
        
        # Sort by created_at (most recent first)
        bookings.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
    except Exception:
        pass
    
    return bookings
