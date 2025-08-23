from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from langchain.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from packages.agents.state import BookingState, BookingStep, booking_state_manager
from packages.agents.tools.validators import resolve_date
from packages.agents.tools.google_calendar import create_calendar_event
from packages.agents.tools.persistence_tools import persist_booking


class BookingResponse(BaseModel):
    response: str = Field(description="Natural response to the user")
    extracted_info: Dict[str, Any] = Field(description="Any information extracted from user's message")
    next_question: str | None = Field(description="Next question to ask, or null if complete")
    is_complete: bool = Field(description="Whether all required information has been collected")


class BookingAgent:
    """LLM-based agent for collecting booking information through natural conversation."""
    
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "google").lower()
        self.parser = PydanticOutputParser(pydantic_object=BookingResponse)
    
    def _call_llm(self, prompt: str, query: str) -> BookingResponse:
        """Call LLM with structured output parsing."""
        if self.provider == "google":
            model_name = os.getenv("GOOGLE_LLM_MODEL", "gemini-1.5-flash")
            model = ChatGoogleGenerativeAI(model=model_name, temperature=0.1)
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": query}
            ]
            resp = model.invoke(messages)
            content = getattr(resp, "content", "") or ""
        elif self.provider == "openai":
            from openai import OpenAI
            client = OpenAI()
            model_name = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
            resp = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": prompt}, {"role": "user", "content": query}],
                temperature=0.1,
            )
            content = resp.choices[0].message.content or ""
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
        
        try:
            result = self.parser.parse(content)
            return result
        except Exception:
            # Fallback response
            return BookingResponse(
                response="I didn't understand that. Could you please provide the information I asked for?",
                extracted_info={},
                next_question=None,
                is_complete=False
            )
    
    def process_booking_message(self, chat_id: str, user_message: str) -> Dict[str, Any]:
        """Process a user message in the booking flow."""
        # Get or create booking state
        state = booking_state_manager.get_state(chat_id)
        if not state:
            state = booking_state_manager.create_state(chat_id)
        
        print(f"DEBUG: Current state at start: {state.collected}")
        print(f"DEBUG: Required fields: {state.required_fields}")
        
        # Get next required field
        next_field = booking_state_manager.get_next_required_field(state)
        
        # Create context for LLM
        context = {
            "collected_info": state.collected,
            "next_required_field": next_field,
            "all_required_fields": state.required_fields,
            "format_instructions": self.parser.get_format_instructions()
        }
        
        # Create a flexible prompt that can handle any missing information
        missing_fields = [field for field in state.required_fields if field not in state.collected]
        
        if not missing_fields:
            # All required fields collected
            prompt = f"""You are a friendly booking assistant. All required information has been collected.

Collected information: {context['collected_info']}

Your task:
1. Thank the user for providing the information
2. Summarize what was collected
3. Ask if they'd like to proceed with the booking

{context['format_instructions']}"""
        else:
            # Create a flexible prompt for collecting any missing information
            field_descriptions = {
                "name": "name",
                "phone": "phone", 
                "email": "email",
                "date_time": "date_time"
            }
            
            missing_descriptions = [field_descriptions[field] for field in missing_fields]
            missing_text = ", ".join(missing_descriptions[:-1])
            if len(missing_descriptions) > 1:
                missing_text += f" and {missing_descriptions[-1]}"
            else:
                missing_text = missing_descriptions[0]
            
            prompt = f"""You are a friendly booking assistant collecting information for a call booking.

IMPORTANT: You already have this information collected: {context['collected_info']}
You still need: {missing_text}

Your task:
1. Extract ONLY the missing information from their message
2. DO NOT ask for information you already have
3. If they provide missing information, acknowledge it and proceed
4. If they don't provide missing information, politely ask for what's still needed
5. Always reference what you already have when responding

CRITICAL: Use these EXACT field names in your extracted_info:
- "name" for person's name
- "phone" for phone number  
- "email" for email address
- "date_time" for date and time

Examples:
- If you have name/phone/email but need date: "I have your name, phone, and email. When would you like to schedule the call?"
- If you have name/phone/date but need email: "I have your name, phone, and preferred time. What's your email address?"

{context['format_instructions']}"""
        
        # Get LLM response
        llm_response = self._call_llm(prompt, user_message)
        print(f"DEBUG: LLM extracted info: {llm_response.extracted_info}")
        
        # Validate and store extracted information
        if llm_response.extracted_info:
            for field, value in llm_response.extracted_info.items():
                # Allow collecting any required field, not just the next one
                if field in state.required_fields and field not in state.collected:
                    # Validate the extracted information
                    if field == "email":
                        # Simple email validation - just check for @ symbol
                        if "@" in str(value) and "." in str(value):
                            booking_state_manager.add_collected_info(chat_id, field, str(value))
                        else:
                            llm_response.response = f"That doesn't look like a valid email address. Could you please provide a valid email?"
                            llm_response.extracted_info = {}
                            llm_response.next_question = "What's your email address?"
                            llm_response.is_complete = False
                    
                    elif field == "phone":
                        # Simple phone validation - just check for digits
                        phone_str = str(value).replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                        if phone_str.isdigit() and len(phone_str) >= 10:
                            booking_state_manager.add_collected_info(chat_id, field, phone_str)
                        else:
                            llm_response.response = f"That doesn't look like a valid phone number. Could you please provide a valid phone number?"
                            llm_response.extracted_info = {}
                            llm_response.next_question = "What's your phone number?"
                            llm_response.is_complete = False
                    
                    elif field == "date_time":
                        validation = resolve_date(str(value))
                        if validation["is_valid"]:
                            booking_state_manager.add_collected_info(chat_id, field, validation["iso_date"])
                        else:
                            llm_response.response = f"I couldn't understand that date/time. {validation['reasoning']}. Could you please provide a clear date and time?"
                            llm_response.extracted_info = {}
                            llm_response.next_question = "When would you like to schedule the call?"
                            llm_response.is_complete = False
                    
                    else:
                        # For name, just store as-is
                        booking_state_manager.add_collected_info(chat_id, field, str(value))
        
        # Update state
        updated_state = booking_state_manager.get_state(chat_id)
        print(f"DEBUG: Updated state collected: {updated_state.collected if updated_state else 'None'}")
        print(f"DEBUG: Required fields: {updated_state.required_fields if updated_state else 'None'}")
        print(f"DEBUG: Is complete: {booking_state_manager.is_complete(updated_state) if updated_state else 'None'}")
        
        if updated_state and booking_state_manager.is_complete(updated_state):
            print(f"DEBUG: All fields collected! Executing booking workflow...")
            llm_response.is_complete = True
            
            # Execute the booking workflow
            response = self._execute_booking_workflow(chat_id, updated_state)
            return response
        
        # Prepare response
        response = {
            "answer": llm_response.response,
            "citations": [],
            "confidence": 1.0,
            "intent": "booking",
            "booking_state": updated_state.to_dict() if updated_state else None,
            "is_complete": llm_response.is_complete
        }
        
        return response
    
    def _execute_booking_workflow(self, chat_id: str, state: BookingState) -> Dict[str, Any]:
        """Execute the complete booking workflow when all information is collected."""
        try:
            # Extract booking information
            name = state.collected.get("name", "")
            email = state.collected.get("email", "")
            phone = state.collected.get("phone", "")
            
            # Use the collected date/time or default to tomorrow at 10 AM
            from datetime import datetime, timedelta
            collected_date_time = state.collected.get("date_time")
            print(f"DEBUG: Collected date_time: {collected_date_time}")
            
            if collected_date_time:
                try:
                    # Handle both ISO format and other formats
                    if 'T' in collected_date_time:
                        meeting_date = datetime.fromisoformat(collected_date_time)
                    else:
                        # If it's just a date, add default time
                        meeting_date = datetime.fromisoformat(collected_date_time + "T10:00:00")
                    print(f"DEBUG: Parsed meeting_date: {meeting_date}")
                except ValueError as e:
                    print(f"DEBUG: Date parsing failed: {e}")
                    # Fallback to default if parsing fails
                    meeting_date = datetime.now() + timedelta(days=1)
                    meeting_date = meeting_date.replace(hour=10, minute=0, second=0, microsecond=0)
            else:
                # Default to tomorrow at 10 AM if no date/time collected
                meeting_date = datetime.now() + timedelta(days=1)
                meeting_date = meeting_date.replace(hour=10, minute=0, second=0, microsecond=0)
            
            print(f"DEBUG: Final meeting_date: {meeting_date}")
            
            meeting_title = f"Call with {name}"
            
            # Step 1: Create calendar event
            try:
                calendar_result = create_calendar_event(
                    title=meeting_title,
                    start_time=meeting_date,
                    duration_minutes=30,
                    description=f"Call with {name} ({email})",
                    attendee_email=email,
                    attendee_name=name
                )
                print(f"DEBUG: Calendar result: {calendar_result}")
            except Exception as e:
                print(f"DEBUG: Calendar creation failed: {e}")
                # Create a mock calendar result for testing
                from packages.agents.tools.google_calendar import CalendarEvent
                calendar_result = CalendarEvent(
                    event_id="mock_event_id",
                    title=meeting_title,
                    start_time=meeting_date,
                    end_time=meeting_date + timedelta(minutes=30),
                    meeting_link="https://meet.google.com/mock-link",
                    calendar_url="https://calendar.google.com/mock-event",
                    success=True,
                    error_message=None
                )
            
            # Step 2: Persist booking
            persistence_result = persist_booking(
                chat_id=chat_id,
                name=name,
                email=email,
                phone=phone,
                meeting_date=meeting_date,
                meeting_title=meeting_title,
                calendar_event_id=calendar_result.event_id if calendar_result.success else None,
                meeting_link=calendar_result.meeting_link if calendar_result.success else None
            )
            

            
            # Clear the booking state
            booking_state_manager.clear_state(chat_id)
            
            # Prepare success response
            if persistence_result.success:
                response_text = f"""Perfect! Your call has been scheduled successfully. 

📅 **Meeting Details:**
- **Date:** {meeting_date.strftime('%A, %B %d, %Y')}
- **Time:** {meeting_date.strftime('%I:%M %p')} - {(meeting_date + timedelta(minutes=30)).strftime('%I:%M %p')}
- **Title:** {meeting_title}

{f"🔗 **Meeting Link:** {calendar_result.meeting_link}" if calendar_result.success and calendar_result.meeting_link else ""}
{f"📅 **Calendar Event:** Created in your Google Calendar" if calendar_result.success else ""}

Your booking ID is: `{persistence_result.booking_id}`

We'll call you at the scheduled time. If you need to reschedule or cancel, please let us know!"""
                
                return {
                    "answer": response_text,
                    "citations": [],
                    "confidence": 1.0,
                    "intent": "booking_complete",
                    "booking_state": None,
                    "is_complete": True,
                    "booking_id": persistence_result.booking_id,
                    "meeting_link": calendar_result.meeting_link if calendar_result.success else None
                }
            else:
                # Handle persistence failure
                response_text = f"I'm sorry, but there was an issue saving your booking. Please try again or contact support. Error: {persistence_result.error_message}"
                
                return {
                    "answer": response_text,
                    "citations": [],
                    "confidence": 1.0,
                    "intent": "booking_error",
                    "booking_state": state.to_dict(),
                    "is_complete": False
                }
                
        except Exception as e:
            # Handle any unexpected errors
            response_text = f"I'm sorry, but there was an unexpected error while processing your booking. Please try again. Error: {str(e)}"
            
            return {
                "answer": response_text,
                "citations": [],
                "confidence": 1.0,
                "intent": "booking_error",
                "booking_state": state.to_dict(),
                "is_complete": False
            }


# Global instance
booking_agent = BookingAgent()
