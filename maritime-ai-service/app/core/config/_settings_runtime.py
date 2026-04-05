"""Runtime helpers for Settings computed properties."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def append_connect_timeout(self, url: str) -> str:
    """Add connect_timeout when missing so local misconfigurations fail fast."""
    if "connect_timeout=" in url:
        return url

    separator = "&" if "?" in url else "?"
    return f"{url}{separator}connect_timeout={self.postgres_connect_timeout_seconds}"


def remove_connect_timeout(self, url: str) -> str:
    """Strip connect_timeout for asyncpg DSNs, which do not accept it as a server setting."""
    if "connect_timeout=" not in url:
        return url

    parts = urlsplit(url)
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key != "connect_timeout"
    ]
    return urlunsplit(parts._replace(query=urlencode(filtered_query)))


def build_postgres_url(self) -> str:
    """Construct PostgreSQL connection URL."""
    if self.database_url:
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        return append_connect_timeout(self, url)

    return append_connect_timeout(
        self,
        f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}",
    )


def build_asyncpg_url(self) -> str:
    """Construct asyncpg-compatible URL (plain postgresql://)."""
    if self.database_url:
        url = self.database_url
        url = url.replace("postgresql+asyncpg://", "postgresql://")
        url = url.replace("postgres://", "postgresql://")
        return remove_connect_timeout(self, url)
    return remove_connect_timeout(
        self,
        f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}",
    )


def build_postgres_url_sync(self) -> str:
    """Construct synchronous PostgreSQL connection URL."""
    if self.database_url:
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        url = url.replace("postgresql+asyncpg://", "postgresql://")
        if "ssl=require" in url:
            url = url.replace("ssl=require", "sslmode=require")
        return append_connect_timeout(self, url)

    return append_connect_timeout(
        self,
        f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}",
    )


def resolve_neo4j_username(self) -> str:
    """Get Neo4j username (supports both neo4j_user and neo4j_username)."""
    return self.neo4j_username or self.neo4j_user


def refresh_nested_views_impl(self) -> None:
    """Refresh nested config snapshots after runtime field mutation."""
    self._sync_nested_groups()
