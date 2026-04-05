"""Support helpers for admin domain-management routes."""

from __future__ import annotations

from typing import Any


def list_domains_impl(
    *,
    registry: Any,
    summary_cls: type,
) -> list[Any]:
    """Build the serialized list of active domain summaries."""
    result = []
    for _, plugin in registry.list_all().items():
        cfg = plugin.get_config()
        skills = plugin.get_skills()
        result.append(
            summary_cls(
                id=cfg.id,
                name=cfg.name,
                name_vi=cfg.name_vi,
                version=cfg.version,
                description=cfg.description,
                skill_count=len(skills),
                keyword_count=len(cfg.routing_keywords),
            )
        )
    return result


def get_domain_detail_impl(
    *,
    registry: Any,
    domain_id: str,
    detail_cls: type,
) -> Any | None:
    """Build the serialized payload for a single domain plugin."""
    plugin = registry.get(domain_id)
    if plugin is None:
        return None

    cfg = plugin.get_config()
    skills = plugin.get_skills()
    hyde = plugin.get_hyde_templates()
    prompts_dir = plugin.get_prompts_dir()

    return detail_cls(
        id=cfg.id,
        name=cfg.name,
        name_vi=cfg.name_vi,
        version=cfg.version,
        description=cfg.description,
        routing_keywords=cfg.routing_keywords,
        mandatory_search_triggers=cfg.mandatory_search_triggers,
        rag_agent_description=cfg.rag_agent_description,
        tutor_agent_description=cfg.tutor_agent_description,
        skills=[
            {"id": skill.id, "name": skill.name, "description": skill.description}
            for skill in skills
        ],
        has_prompts=prompts_dir.exists() if prompts_dir else False,
        has_hyde_templates=len(hyde) > 0,
    )


def list_domain_skills_impl(
    *,
    registry: Any,
    domain_id: str,
    skill_detail_cls: type,
) -> list[Any] | None:
    """Build the serialized skill list for a single domain plugin."""
    plugin = registry.get(domain_id)
    if plugin is None:
        return None

    result = []
    for skill in plugin.get_skills():
        content = plugin.activate_skill(skill.id)
        result.append(
            skill_detail_cls(
                id=skill.id,
                name=skill.name,
                description=skill.description,
                domain_id=skill.domain_id,
                version=skill.version,
                triggers=skill.triggers,
                content_length=len(content) if content else 0,
            )
        )
    return result
