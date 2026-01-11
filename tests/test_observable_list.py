"""Tests for ObservableList class."""

from typing import Any

import pytest
from pvm.common import ObservableList


class TestObservableListInit:
    """Tests for ObservableList initialization."""

    def test_init_empty(self) -> None:
        """Test creating an empty observable list."""
        obs_list: ObservableList[int] = ObservableList()
        assert len(obs_list) == 0
        assert list(obs_list) == []

    def test_init_with_iterable(self) -> None:
        """Test creating an observable list with initial values."""
        obs_list = ObservableList([1, 2, 3])
        assert len(obs_list) == 3
        assert list(obs_list) == [1, 2, 3]

    def test_init_with_callback(self) -> None:
        """Test creating an observable list with a callback."""
        callback_count = 0

        def on_mutate() -> None:
            nonlocal callback_count
            callback_count += 1

        obs_list = ObservableList([1, 2], on_mutate=on_mutate)
        assert len(obs_list) == 2
        # Callback should not be triggered on init
        assert callback_count == 0


class TestObservableListAppend:
    """Tests for ObservableList.append."""

    def test_append_triggers_callback(self) -> None:
        """Test that append triggers the callback."""
        callback_count = 0

        def on_mutate() -> None:
            nonlocal callback_count
            callback_count += 1

        obs_list = ObservableList([1], on_mutate=on_mutate)
        obs_list.append(2)
        assert list(obs_list) == [1, 2]
        assert callback_count == 1

    def test_append_without_callback(self) -> None:
        """Test that append works without a callback."""
        obs_list: ObservableList[int] = ObservableList([1])
        obs_list.append(2)
        assert list(obs_list) == [1, 2]


class TestObservableListExtend:
    """Tests for ObservableList.extend."""

    def test_extend_triggers_callback(self) -> None:
        """Test that extend triggers the callback."""
        callback_count = 0

        def on_mutate() -> None:
            nonlocal callback_count
            callback_count += 1

        obs_list = ObservableList([1], on_mutate=on_mutate)
        obs_list.extend([2, 3])
        assert list(obs_list) == [1, 2, 3]
        assert callback_count == 1

    def test_extend_without_callback(self) -> None:
        """Test that extend works without a callback."""
        obs_list: ObservableList[int] = ObservableList([1])
        obs_list.extend([2, 3])
        assert list(obs_list) == [1, 2, 3]


class TestObservableListInsert:
    """Tests for ObservableList.insert."""

    def test_insert_triggers_callback(self) -> None:
        """Test that insert triggers the callback."""
        callback_count = 0

        def on_mutate() -> None:
            nonlocal callback_count
            callback_count += 1

        obs_list = ObservableList([1, 3], on_mutate=on_mutate)
        obs_list.insert(1, 2)
        assert list(obs_list) == [1, 2, 3]
        assert callback_count == 1

    def test_insert_at_beginning(self) -> None:
        """Test inserting at the beginning of the list."""
        obs_list = ObservableList([2, 3])
        obs_list.insert(0, 1)
        assert list(obs_list) == [1, 2, 3]

    def test_insert_at_end(self) -> None:
        """Test inserting at the end of the list."""
        obs_list = ObservableList([1, 2])
        obs_list.insert(2, 3)
        assert list(obs_list) == [1, 2, 3]


class TestObservableListRemove:
    """Tests for ObservableList.remove."""

    def test_remove_triggers_callback(self) -> None:
        """Test that remove triggers the callback."""
        callback_count = 0

        def on_mutate() -> None:
            nonlocal callback_count
            callback_count += 1

        obs_list = ObservableList([1, 2, 3], on_mutate=on_mutate)
        obs_list.remove(2)
        assert list(obs_list) == [1, 3]
        assert callback_count == 1

    def test_remove_nonexistent_raises(self) -> None:
        """Test that removing a nonexistent item raises ValueError."""
        obs_list = ObservableList([1, 2, 3])
        with pytest.raises(ValueError, match="not in list"):
            obs_list.remove(4)


class TestObservableListPop:
    """Tests for ObservableList.pop."""

    def test_pop_triggers_callback(self) -> None:
        """Test that pop triggers the callback."""
        callback_count = 0

        def on_mutate() -> None:
            nonlocal callback_count
            callback_count += 1

        obs_list = ObservableList([1, 2, 3], on_mutate=on_mutate)
        result = obs_list.pop()
        assert result == 3
        assert list(obs_list) == [1, 2]
        assert callback_count == 1

    def test_pop_with_index(self) -> None:
        """Test popping at a specific index."""
        obs_list = ObservableList([1, 2, 3])
        result = obs_list.pop(0)
        assert result == 1
        assert list(obs_list) == [2, 3]

    def test_pop_empty_raises(self) -> None:
        """Test that popping from an empty list raises IndexError."""
        obs_list: ObservableList[int] = ObservableList()
        with pytest.raises(IndexError):
            obs_list.pop()


class TestObservableListClear:
    """Tests for ObservableList.clear."""

    def test_clear_triggers_callback(self) -> None:
        """Test that clear triggers the callback."""
        callback_count = 0

        def on_mutate() -> None:
            nonlocal callback_count
            callback_count += 1

        obs_list = ObservableList([1, 2, 3], on_mutate=on_mutate)
        obs_list.clear()
        assert list(obs_list) == []
        assert callback_count == 1

    def test_clear_empty_list(self) -> None:
        """Test clearing an already empty list."""
        callback_count = 0

        def on_mutate() -> None:
            nonlocal callback_count
            callback_count += 1

        obs_list: ObservableList[int] = ObservableList(on_mutate=on_mutate)
        obs_list.clear()
        assert list(obs_list) == []
        assert callback_count == 1  # Still triggers callback


class TestObservableListSetItem:
    """Tests for ObservableList.__setitem__."""

    def test_setitem_triggers_callback(self) -> None:
        """Test that setting an item triggers the callback."""
        callback_count = 0

        def on_mutate() -> None:
            nonlocal callback_count
            callback_count += 1

        obs_list = ObservableList([1, 2, 3], on_mutate=on_mutate)
        obs_list[1] = 20
        assert list(obs_list) == [1, 20, 3]
        assert callback_count == 1

    def test_setitem_slice(self) -> None:
        """Test setting a slice triggers the callback."""
        callback_count = 0

        def on_mutate() -> None:
            nonlocal callback_count
            callback_count += 1

        obs_list = ObservableList([1, 2, 3, 4], on_mutate=on_mutate)
        obs_list[1:3] = [20, 30]
        assert list(obs_list) == [1, 20, 30, 4]
        assert callback_count == 1


class TestObservableListDelItem:
    """Tests for ObservableList.__delitem__."""

    def test_delitem_triggers_callback(self) -> None:
        """Test that deleting an item triggers the callback."""
        callback_count = 0

        def on_mutate() -> None:
            nonlocal callback_count
            callback_count += 1

        obs_list = ObservableList([1, 2, 3], on_mutate=on_mutate)
        del obs_list[1]
        assert list(obs_list) == [1, 3]
        assert callback_count == 1

    def test_delitem_slice(self) -> None:
        """Test deleting a slice triggers the callback."""
        callback_count = 0

        def on_mutate() -> None:
            nonlocal callback_count
            callback_count += 1

        obs_list = ObservableList([1, 2, 3, 4], on_mutate=on_mutate)
        del obs_list[1:3]
        assert list(obs_list) == [1, 4]
        assert callback_count == 1


class TestObservableListIAdd:
    """Tests for ObservableList.__iadd__ (+=)."""

    def test_iadd_triggers_callback(self) -> None:
        """Test that += triggers the callback."""
        callback_count = 0

        def on_mutate() -> None:
            nonlocal callback_count
            callback_count += 1

        obs_list = ObservableList([1], on_mutate=on_mutate)
        obs_list += [2, 3]
        assert list(obs_list) == [1, 2, 3]
        assert callback_count == 1

    def test_iadd_returns_same_list(self) -> None:
        """Test that += returns the same ObservableList instance."""
        obs_list = ObservableList([1])
        original_id = id(obs_list)
        obs_list += [2, 3]
        assert id(obs_list) == original_id
        assert isinstance(obs_list, ObservableList)


class TestObservableListMultipleMutations:
    """Tests for multiple mutations on ObservableList."""

    def test_multiple_mutations_trigger_multiple_callbacks(self) -> None:
        """Test that each mutation triggers a separate callback."""
        callback_count = 0

        def on_mutate() -> None:
            nonlocal callback_count
            callback_count += 1

        obs_list = ObservableList([1], on_mutate=on_mutate)
        obs_list.append(2)  # +1
        obs_list.extend([3, 4])  # +1
        obs_list.pop()  # +1
        obs_list[0] = 10  # +1
        assert callback_count == 4

    def test_list_behavior_preserved(self) -> None:
        """Test that ObservableList behaves like a regular list."""
        obs_list = ObservableList([1, 2, 3])

        # Test indexing
        assert obs_list[0] == 1
        assert obs_list[-1] == 3

        # Test slicing
        assert obs_list[1:] == [2, 3]

        # Test iteration
        assert sum(obs_list) == 6

        # Test contains
        assert 2 in obs_list
        assert 4 not in obs_list

        # Test len
        assert len(obs_list) == 3

    def test_callback_receives_no_arguments(self) -> None:
        """Test that the callback receives no arguments."""
        received_args: list[tuple[Any, ...]] = []

        def on_mutate(*args: Any) -> None:
            received_args.append(args)

        obs_list = ObservableList([1], on_mutate=on_mutate)
        obs_list.append(2)
        assert received_args == [()]
