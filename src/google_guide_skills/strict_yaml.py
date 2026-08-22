"""YAML loading that refuses silently shadowed mapping keys."""

from __future__ import annotations

from typing import Any

import yaml


class DuplicateKeyError(yaml.YAMLError):
    """Raised when a YAML mapping repeats a key."""


class UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader variant with duplicate-key rejection."""


def _construct_unique_mapping(
    loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            hash(key)
        except TypeError as exc:
            raise DuplicateKeyError(
                f"YAML mapping keys must be hashable scalars: {key!r}"
            ) from exc
        if key in mapping:
            raise DuplicateKeyError(f"Duplicate YAML mapping key: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def strict_safe_load(text: str) -> object:
    return yaml.load(text, Loader=UniqueKeyLoader)
