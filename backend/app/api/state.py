from __future__ import annotations

from typing import Optional


class DatasetState:
    instance: Optional[object] = None


def get_dataset() -> object:
    if DatasetState.instance is None:
        raise RuntimeError("dataset not loaded; lifespan must run first")
    return DatasetState.instance


def set_dataset(dataset: object) -> None:
    DatasetState.instance = dataset
