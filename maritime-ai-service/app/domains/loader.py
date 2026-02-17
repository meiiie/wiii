"""
Domain Loader - Auto-discovery of domain plugins.

Scans app/domains/*/domain.yaml at startup.
Imports each domain's __init__.py and instantiates the DomainPlugin subclass.
"""

import importlib
import logging
from pathlib import Path
from typing import List


from app.domains.base import DomainPlugin, YamlDomainPlugin

logger = logging.getLogger(__name__)


class DomainLoader:
    """
    Auto-discovers and loads domain plugins from the filesystem.

    Convention:
        app/domains/{domain_id}/
        +-- __init__.py       # Must export a DomainPlugin subclass
        +-- domain.yaml       # Domain manifest (required for discovery)
    """

    def __init__(self, domains_dir: Path):
        """
        Args:
            domains_dir: Path to app/domains/ directory
        """
        self._domains_dir = domains_dir

    def discover(self) -> List[DomainPlugin]:
        """
        Discover and instantiate all domain plugins.

        Scans for domains/*/domain.yaml files.
        Imports each domain's __init__.py module.
        Looks for a DomainPlugin subclass and instantiates it.

        Returns:
            List of instantiated DomainPlugin objects
        """
        plugins = []

        if not self._domains_dir.exists():
            logger.warning("Domains directory not found: %s", self._domains_dir)
            return plugins

        for entry in sorted(self._domains_dir.iterdir()):
            # Skip non-directories and special directories
            if not entry.is_dir():
                continue
            if entry.name.startswith("_") or entry.name.startswith("."):
                continue

            manifest_path = entry / "domain.yaml"
            init_path = entry / "__init__.py"

            if not manifest_path.exists():
                logger.debug("Skipping %s: no domain.yaml", entry.name)
                continue

            if not init_path.exists():
                logger.warning("Skipping %s: no __init__.py", entry.name)
                continue

            try:
                plugin = self._load_domain(entry.name)
                if plugin:
                    plugins.append(plugin)
                    logger.info("Discovered domain plugin: %s", entry.name)
            except Exception as e:
                logger.error("Failed to load domain '%s': %s", entry.name, e)

        logger.info("Domain discovery complete: %d plugin(s) found", len(plugins))
        return plugins

    def _load_domain(self, domain_name: str) -> DomainPlugin | None:
        """
        Load a single domain plugin by importing its module.

        Args:
            domain_name: Directory name under app/domains/

        Returns:
            DomainPlugin instance or None
        """
        module_path = f"app.domains.{domain_name}"

        try:
            module = importlib.import_module(module_path)
        except Exception as e:
            logger.error("Failed to import %s: %s", module_path, e)
            return None

        # Find DomainPlugin subclass in module
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, DomainPlugin)
                and attr not in (DomainPlugin, YamlDomainPlugin)
            ):
                try:
                    instance = attr()
                    logger.info("Instantiated %s from %s", attr.__name__, module_path)
                    return instance
                except Exception as e:
                    logger.error("Failed to instantiate %s: %s", attr.__name__, e)
                    return None

        logger.warning("No DomainPlugin subclass found in %s", module_path)
        return None
