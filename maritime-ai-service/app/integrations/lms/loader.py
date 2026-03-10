"""
LMS Connector Loader — Auto-discovery + Bootstrap

Sprint 155b: Multi-LMS Plugin Architecture

Loads LMS connector adapters from configuration and registers them.
Supports backward compatibility with Sprint 155 flat config fields.
"""

import json
import logging
from typing import List

from app.integrations.lms.base import LMSBackendType, LMSConnectorConfig
from app.integrations.lms.registry import get_lms_connector_registry

logger = logging.getLogger(__name__)

# Map backend_type string → factory function
_ADAPTER_FACTORIES = {}


def _register_builtin_factories():
    """Register built-in adapter factories (lazy to avoid circular imports)."""
    if _ADAPTER_FACTORIES:
        return

    def _create_spring_boot(config: LMSConnectorConfig):
        from app.integrations.lms.connectors.spring_boot import SpringBootLMSAdapter
        return SpringBootLMSAdapter(config)

    _ADAPTER_FACTORIES[LMSBackendType.SPRING_BOOT] = _create_spring_boot
    # Future: add moodle, canvas, etc.


def _parse_connector_configs(settings) -> List[LMSConnectorConfig]:
    """Parse connector configs from settings.lms_connectors JSON string."""
    raw = getattr(settings, "lms_connectors", "[]")
    if not raw or raw == "[]":
        return []
    try:
        items = json.loads(raw) if isinstance(raw, str) else raw
        configs = []
        for item in items:
            backend_str = item.get("backend_type", "spring_boot")
            try:
                backend = LMSBackendType(backend_str)
            except ValueError:
                logger.warning("Unknown LMS backend_type '%s', skipping", backend_str)
                continue
            configs.append(LMSConnectorConfig(
                id=item["id"],
                display_name=item.get("display_name", item["id"]),
                backend_type=backend,
                base_url=item.get("base_url", ""),
                service_token=item.get("service_token"),
                webhook_secret=item.get("webhook_secret"),
                api_timeout=item.get("api_timeout", 10),
                signature_header=item.get("signature_header", "X-LMS-Signature"),
                auth_type=item.get("auth_type", "bearer_token"),
                enabled=item.get("enabled", True),
                organization_id=item.get("organization_id"),
                extra=item.get("extra", {}),
            ))
        return configs
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        logger.error("Failed to parse lms_connectors config: %s", e)
        return []


def _auto_migrate_flat_config(settings) -> List[LMSConnectorConfig]:
    """Backward compat: create a connector from Sprint 155 flat fields.

    If lms_connectors is empty but old flat fields (lms_base_url etc.) are set,
    auto-create a 'default' Spring Boot connector.
    """
    base_url = getattr(settings, "lms_base_url", None)
    if not base_url:
        return []

    logger.info(
        "Auto-migrating flat LMS config to connector format "
        "(set LMS_CONNECTORS env var to suppress this)"
    )
    return [LMSConnectorConfig(
        id="default",
        display_name="Default LMS",
        backend_type=LMSBackendType.SPRING_BOOT,
        base_url=base_url,
        service_token=getattr(settings, "lms_service_token", None),
        webhook_secret=getattr(settings, "lms_webhook_secret", None),
        api_timeout=getattr(settings, "lms_api_timeout", 10),
        enabled=True,
    )]


def bootstrap_lms_connectors(settings=None) -> int:
    """Load and register all LMS connectors from config.

    Call during app startup (lifespan). Returns number of connectors registered.
    """
    if settings is None:
        from app.core.config import get_settings
        settings = get_settings()

    if not getattr(settings, "enable_lms_integration", False):
        logger.debug("LMS integration disabled")
        return 0

    _register_builtin_factories()
    registry = get_lms_connector_registry()

    # Try new multi-connector config first, then fall back to flat fields
    configs = _parse_connector_configs(settings)
    if not configs:
        configs = _auto_migrate_flat_config(settings)

    registered = 0
    for config in configs:
        factory = _ADAPTER_FACTORIES.get(config.backend_type)
        if factory is None:
            logger.warning(
                "No adapter factory for backend_type '%s' (connector '%s')",
                config.backend_type.value, config.id,
            )
            continue
        try:
            adapter = factory(config)
            registry.register(adapter)
            registered += 1
        except Exception as e:
            logger.error("Failed to create LMS connector '%s': %s", config.id, e)

    logger.info("LMS integration: %d connector(s) registered", registered)
    return registered
