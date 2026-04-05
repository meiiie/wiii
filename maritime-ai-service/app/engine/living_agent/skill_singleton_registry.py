"""Shared singleton registry for living-agent skill services.

Builder and learner both need access to each other as singletons, but they do
not need to import each other's modules directly to do that.
"""

from __future__ import annotations

from typing import Any, Callable

_builder_instance: Any | None = None
_learner_instance: Any | None = None
_builder_factory: Callable[[], Any] | None = None
_learner_factory: Callable[[], Any] | None = None


def get_registered_skill_builder():
    return _builder_instance


def set_registered_skill_builder(builder):
    global _builder_instance
    _builder_instance = builder
    return builder


def get_registered_skill_learner():
    return _learner_instance


def set_registered_skill_learner(learner):
    global _learner_instance
    _learner_instance = learner
    return learner


def register_skill_builder_factory(factory: Callable[[], Any]) -> None:
    global _builder_factory
    _builder_factory = factory


def register_skill_learner_factory(factory: Callable[[], Any]) -> None:
    global _learner_factory
    _learner_factory = factory


def get_or_create_registered_skill_builder():
    builder = get_registered_skill_builder()
    if builder is None and _builder_factory is not None:
        builder = set_registered_skill_builder(_builder_factory())
    return builder


def get_or_create_registered_skill_learner():
    learner = get_registered_skill_learner()
    if learner is None and _learner_factory is not None:
        learner = set_registered_skill_learner(_learner_factory())
    return learner
