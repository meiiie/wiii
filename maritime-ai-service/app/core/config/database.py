"""DatabaseConfig — PostgreSQL + async pool configuration."""
from typing import Optional

from pydantic import BaseModel


class DatabaseConfig(BaseModel):
    """PostgreSQL + async pool configuration."""
    host: str = "localhost"
    port: int = 5433
    user: str = "wiii"
    password: str = "wiii_secret"
    db: str = "wiii_ai"
    database_url: Optional[str] = None
    async_pool_min_size: int = 10
    async_pool_max_size: int = 50
