from __future__ import annotations

import os
from typing import Any, Dict

from langchain.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field


class BookingIntent(BaseModel):
    is_booking_intent: bool = Field(description="Whether the user wants to book a call/appointment")
    confidence: float = Field(description="Confidence score between 0 and 1", ge=0, le=1)
    reasoning: str = Field(description="Brief explanation for the classification")


def detect_booking_intent(query: str) -> Dict[str, Any]:
    """Detect if user wants to book a call/appointment using LLM.

    Returns: {is_booking_intent: bool, confidence: float, reasoning: str}
    """
    provider = os.getenv("LLM_PROVIDER", "google").lower()
    
    # Create parser
    parser = PydanticOutputParser(pydantic_object=BookingIntent)
    
    if provider == "google":
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a booking intent classifier. Analyze if the user wants to book a call, appointment, or schedule a meeting.

Look for phrases like: "call me", "book", "schedule", "appointment", "meeting", "set up a call", "can you call", "i need to book".

{format_instructions}"""),
            ("human", "User query: {query}"),
        ])
        model_name = os.getenv("GOOGLE_LLM_MODEL", "gemini-1.5-flash")
        model = ChatGoogleGenerativeAI(model=model_name, temperature=0.1)
        messages = prompt.format_messages(
            query=query,
            format_instructions=parser.get_format_instructions()
        )
        resp = model.invoke(messages)
        content = getattr(resp, "content", "") or ""
        try:
            result = parser.parse(content)
            return {
                "is_booking_intent": result.is_booking_intent,
                "confidence": result.confidence,
                "reasoning": result.reasoning
            }
        except Exception:
            return {"is_booking_intent": False, "confidence": 0.0, "reasoning": "Parse error"}
    elif provider == "openai":
        from openai import OpenAI

        client = OpenAI()
        model_name = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
        system = f"""You are a booking intent classifier. Analyze if the user wants to book a call, appointment, or schedule a meeting.

Look for phrases like: "call me", "book", "schedule", "appointment", "meeting", "set up a call", "can you call", "i need to book".

{parser.get_format_instructions()}"""
        resp = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": f"User query: {query}"}],
            temperature=0.1,
        )
        content = resp.choices[0].message.content or ""
        try:
            result = parser.parse(content)
            return {
                "is_booking_intent": result.is_booking_intent,
                "confidence": result.confidence,
                "reasoning": result.reasoning
            }
        except Exception:
            return {"is_booking_intent": False, "confidence": 0.0, "reasoning": "Parse error"}
    else:
        return {"is_booking_intent": False, "confidence": 0.0, "reasoning": "Unsupported provider"}


__all__ = ["detect_booking_intent"]
