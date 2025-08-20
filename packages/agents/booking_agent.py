from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from langchain.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from packages.agents.state import BookingState, BookingStep, booking_state_manager
from packages.agents.tools.validators import validate_email, validate_phone, resolve_date


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
        
        # Get next required field
        next_field = booking_state_manager.get_next_required_field(state)
        
        # Create context for LLM
        context = {
            "collected_info": state.collected,
            "next_required_field": next_field,
            "all_required_fields": state.required_fields,
            "format_instructions": self.parser.get_format_instructions()
        }
        
        # Create prompt based on what we're collecting
        if next_field == "name":
            prompt = f"""You are a friendly booking assistant collecting information for a call booking.

Current collected information: {context['collected_info']}
Next field to collect: {next_field}

Your task:
1. Extract the person's name from their message
2. Respond naturally and warmly
3. If name is provided, acknowledge it and ask for the next piece of information
4. If name is not provided, politely ask for it

{context['format_instructions']}"""
        
        elif next_field == "phone":
            prompt = f"""You are a friendly booking assistant collecting information for a call booking.

Current collected information: {context['collected_info']}
Next field to collect: {next_field}

Your task:
1. Extract the phone number from their message
2. Respond naturally and warmly
3. If phone number is provided, acknowledge it and ask for the next piece of information
4. If phone number is not provided, politely ask for it

{context['format_instructions']}"""
        
        elif next_field == "email":
            prompt = f"""You are a friendly booking assistant collecting information for a call booking.

Current collected information: {context['collected_info']}
Next field to collect: {next_field}

Your task:
1. Extract the email address from their message
2. Respond naturally and warmly
3. If email is provided, acknowledge it and ask for the next piece of information
4. If email is not provided, politely ask for it

{context['format_instructions']}"""
        
        else:
            # All required fields collected
            prompt = f"""You are a friendly booking assistant. All required information has been collected.

Collected information: {context['collected_info']}

Your task:
1. Thank the user for providing the information
2. Summarize what was collected
3. Ask if they'd like to proceed with the booking

{context['format_instructions']}"""
        
        # Get LLM response
        llm_response = self._call_llm(prompt, user_message)
        
        # Validate and store extracted information
        if llm_response.extracted_info:
            for field, value in llm_response.extracted_info.items():
                if field in state.required_fields and field not in state.collected:
                    # Validate the extracted information
                    if field == "email":
                        validation = validate_email(str(value))
                        if validation["is_valid"]:
                            booking_state_manager.add_collected_info(chat_id, field, validation["normalized"])
                        else:
                            llm_response.response = f"I couldn't validate that email address. {validation['reasoning']}. Could you please provide a valid email?"
                            llm_response.extracted_info = {}
                            llm_response.next_question = "What's your email address?"
                            llm_response.is_complete = False
                    
                    elif field == "phone":
                        validation = validate_phone(str(value))
                        if validation["is_valid"]:
                            booking_state_manager.add_collected_info(chat_id, field, validation["e164"])
                        else:
                            llm_response.response = f"I couldn't validate that phone number. {validation['reasoning']}. Could you please provide a valid phone number?"
                            llm_response.extracted_info = {}
                            llm_response.next_question = "What's your phone number?"
                            llm_response.is_complete = False
                    
                    else:
                        # For name, just store as-is
                        booking_state_manager.add_collected_info(chat_id, field, str(value))
        
        # Update state
        updated_state = booking_state_manager.get_state(chat_id)
        if updated_state and booking_state_manager.is_complete(updated_state):
            llm_response.is_complete = True
        
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


# Global instance
booking_agent = BookingAgent()
