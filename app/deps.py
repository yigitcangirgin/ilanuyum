"""Shared FastAPI dependencies."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.llm import AnthropicClient, LLMClient, OpenAIClient
from app.models import User
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbSession) -> User:
    credentials_error = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    subject = decode_access_token(token)
    if subject is None:
        raise credentials_error
    try:
        user_id = int(subject)
    except ValueError:
        raise credentials_error from None
    user = db.get(User, user_id)
    if user is None:
        raise credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_llm_client() -> Iterator[LLMClient]:
    """Yield the configured LLM client (closed after the request), or answer 503."""
    model = settings.resolved_llm_model
    timeout = settings.llm_timeout_seconds
    client: AnthropicClient | OpenAIClient
    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        client = AnthropicClient(settings.anthropic_api_key, model, timeout)
    elif settings.llm_provider == "openai" and settings.openai_api_key:
        client = OpenAIClient(settings.openai_api_key, model, timeout)
    else:
        raise HTTPException(
            status_code=503,
            detail="Match analysis is not configured: set the API key for LLM_PROVIDER",
        )
    try:
        yield client
    finally:
        client.close()


Llm = Annotated[LLMClient, Depends(get_llm_client)]
