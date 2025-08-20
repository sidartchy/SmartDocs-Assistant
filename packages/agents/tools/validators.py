from __future__ import annotations

import os
import re
from typing import Any, Dict

from langchain.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field


class EmailValidation(BaseModel):
    is_valid: bool = Field(description="Whether the email is valid")
    normalized: str | None = Field(description="Normalized email address in lowercase, or null if invalid")
    reasoning: str = Field(description="Explanation for the validation result")


class PhoneValidation(BaseModel):
    is_valid: bool = Field(description="Whether the phone number is valid")
    e164: str | None = Field(description="Phone number in E.164 format (+country_code_number), or null if invalid")
    reasoning: str = Field(description="Explanation for the validation result")


class DateValidation(BaseModel):
    is_valid: bool = Field(description="Whether the date could be parsed")
    iso_date: str | None = Field(description="Date in ISO format (YYYY-MM-DD), or null if invalid")
    natural_text: str = Field(description="Original natural language text")
    reasoning: str = Field(description="Explanation for the parsing result")


def _call_llm_structured(prompt: str, query: str, parser: PydanticOutputParser) -> Dict[str, Any]:
    """Call LLM with structured output parser."""
    provider = os.getenv("LLM_PROVIDER", "google").lower()
    if provider == "google":
        model_name = os.getenv("GOOGLE_LLM_MODEL", "gemini-1.5-flash")
        model = ChatGoogleGenerativeAI(model=model_name, temperature=0.1)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": query}
        ]
        resp = model.invoke(messages)
        content = getattr(resp, "content", "") or ""
        try:
            result = parser.parse(content)
            return result.model_dump()
        except Exception:
            return {"is_valid": False, "reasoning": "Parse error"}
    elif provider == "openai":
        from openai import OpenAI
        client = OpenAI()
        model_name = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
        resp = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": query}],
            temperature=0.1,
        )
        content = resp.choices[0].message.content or ""
        try:
            result = parser.parse(content)
            return result.model_dump()
        except Exception:
            return {"is_valid": False, "reasoning": "Parse error"}
    else:
        return {"is_valid": False, "reasoning": "Unsupported provider"}


def validate_email(email: str) -> Dict[str, Any]:
    """Validate and normalize email using LLM for edge cases."""
    email = (email or "").strip()
    if not email:
        return {"is_valid": False, "normalized": None, "reasoning": "Empty email"}

    # Basic regex check first
    EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    if not EMAIL_REGEX.match(email):
        return {"is_valid": False, "normalized": None, "reasoning": "Invalid email format"}

    # LLM validation for edge cases and normalization
    parser = PydanticOutputParser(pydantic_object=EmailValidation)
    prompt = f"""You are an email validator. Validate and normalize the email address.

Handle edge cases like:
- Common typos (gmail.com vs gmal.com)
- Extra spaces or formatting
- Case normalization
- Domain validation

{parser.get_format_instructions()}"""

    result = _call_llm_structured(prompt, f"Email: {email}", parser)
    if result.get("is_valid", False):
        return {
            "is_valid": True,
            "normalized": result.get("normalized", email.lower()),
            "reasoning": result.get("reasoning", "Valid email")
        }
    return {"is_valid": False, "normalized": None, "reasoning": result.get("reasoning", "Invalid email")}


def validate_phone(phone: str, region: str | None = None) -> Dict[str, Any]:
    """Validate and format phone number using LLM for natural language parsing."""
    phone = (phone or "").strip()
    if not phone:
        return {"is_valid": False, "e164": None, "reasoning": "Empty phone number"}

    region_code = (region or os.getenv("DEFAULT_REGION") or "NP").upper()

    parser = PydanticOutputParser(pydantic_object=PhoneValidation)
    prompt = f"""You are a phone number validator. Parse and validate the phone number. Convert to E.164 format.

Region: {region_code}
Handle various formats: international, local, with/without country codes, spaces, dashes.

{parser.get_format_instructions()}"""

    result = _call_llm_structured(prompt, f"Phone: {phone}", parser)
    if result.get("is_valid", False):
        return {
            "is_valid": True,
            "e164": result.get("e164"),
            "reasoning": result.get("reasoning", "Valid phone number")
        }
    return {"is_valid": False, "e164": None, "reasoning": result.get("reasoning", "Invalid phone number")}


def resolve_date(text: str, tz: str | None = None) -> Dict[str, Any]:
    """Resolve natural language date/time using LLM for flexible parsing."""
    phrase = (text or "").strip()
    if not phrase:
        return {"is_valid": False, "iso_date": None, "natural_text": "", "reasoning": "Empty date"}

    timezone_str = tz or os.getenv("DEFAULT_TZ") or "Asia/Kathmandu"

    parser = PydanticOutputParser(pydantic_object=DateValidation)
    prompt = f"""You are a date parser. Parse natural language date/time to ISO format.

Timezone: {timezone_str}
Handle phrases like: "next Monday", "tomorrow at 3pm", "in 2 weeks", "next month".

{parser.get_format_instructions()}"""

    result = _call_llm_structured(prompt, f"Date phrase: {phrase}", parser)
    if result.get("is_valid", False):
        return {
            "is_valid": True,
            "iso_date": result.get("iso_date"),
            "natural_text": result.get("natural_text", phrase),
            "reasoning": result.get("reasoning", "Valid date")
        }
    return {
        "is_valid": False,
        "iso_date": None,
        "natural_text": phrase,
        "reasoning": result.get("reasoning", "Invalid date")
    }


__all__ = ["validate_email", "validate_phone", "resolve_date"]


