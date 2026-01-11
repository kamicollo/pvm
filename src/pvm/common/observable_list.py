"""Observable list that notifies on mutations."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, TypeVar

_L = TypeVar("_L")


class ObservableList(list[_L]):
    """A list that notifies a callback when mutated."""

    def __init__(self, iterable: Iterable[_L] | None = None, on_mutate: Callable[[], None] | None = None) -> None:
        """Initialize the observable list."""
        super().__init__(iterable or [])
        self._on_mutate = on_mutate

    def _notify(self) -> None:
        if self._on_mutate:
            self._on_mutate()

    def append(self, value: _L) -> None:  # noqa: D102
        super().append(value)
        self._notify()

    def extend(self, values: Iterable[_L]) -> None:  # noqa: D102
        super().extend(values)
        self._notify()

    def insert(self, index: int, value: _L) -> None:  # noqa: D102  # type: ignore[override]
        super().insert(index, value)
        self._notify()

    def remove(self, value: _L) -> None:  # noqa: D102
        super().remove(value)
        self._notify()

    def pop(self, index: int = -1) -> _L:  # noqa: D102  # type: ignore[override]
        result = super().pop(index)
        self._notify()
        return result

    def clear(self) -> None:  # noqa: D102
        super().clear()
        self._notify()

    def __setitem__(self, index: Any, value: Any) -> None:  # noqa: ANN401, D105
        super().__setitem__(index, value)
        self._notify()

    def __delitem__(self, index: Any) -> None:  # noqa: ANN401, D105
        super().__delitem__(index)
        self._notify()

    def __iadd__(self, values: Iterable[_L]) -> ObservableList[_L]:  # noqa: D105  # type: ignore[override, misc]
        super().__iadd__(values)
        self._notify()
        return self
