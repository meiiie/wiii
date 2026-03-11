"""LMSIntegrationConfig — Spring Boot LMS webhook + API (Sprint 155)."""
from typing import Optional

from pydantic import BaseModel


class LMSIntegrationConfig(BaseModel):
    """LMS integration — Spring Boot LMS webhook + API (Sprint 155)."""
    enabled: bool = False
    base_url: Optional[str] = None
    service_token: Optional[str] = None
    webhook_secret: Optional[str] = None
    api_timeout: int = 10
