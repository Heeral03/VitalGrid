import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.tree_manager import TreeManager, create_default_hospital_tree

@pytest.fixture
def tm():
    root = create_default_hospital_tree()
    return TreeManager(root)

def test_initial_tree_structure(tm):
    assert tm.get_node("hospital-1") is not None
    assert tm.get_node("ward-Alpha") is not None
    assert tm.get_node("bed-101A") is not None
    assert tm.get_node("bed-101A").is_locked is False

def test_lock_bed_success(tm):
    success, msg = tm.lock("bed-101A", "nurse-jones")
    assert success is True
    bed = tm.get_node("bed-101A")
    assert bed.is_locked is True
    assert bed.locked_by == "nurse-jones"
    assert bed.ttl_remaining > 0

    # Ancestor counters
    assert tm.get_node("room-101").locked_descendant_count == 1
    assert tm.get_node("dept-ICU").locked_descendant_count == 1
    assert tm.get_node("ward-Alpha").locked_descendant_count == 1
    assert tm.get_node("hospital-1").locked_descendant_count == 1

def test_lock_duplicate_failure(tm):
    tm.lock("bed-101A", "nurse-jones")
    success, msg = tm.lock("bed-101A", "dr-smith")
    assert success is False
    assert "already exclusively locked" in msg

def test_lock_child_when_ancestor_locked(tm):
    tm.lock("room-101", "dr-smith")
    success, msg = tm.lock("bed-101A", "nurse-jones")
    assert success is False
    assert "ancestor 'room-101' is locked" in msg

def test_lock_ancestor_when_child_locked(tm):
    tm.lock("bed-101A", "nurse-jones")
    success, msg = tm.lock("room-101", "dr-smith")
    assert success is False
    assert "locked descendant(s)" in msg

def test_unlock_success(tm):
    tm.lock("bed-101A", "nurse-jones")
    success, msg = tm.unlock("bed-101A", "nurse-jones")
    assert success is True
    assert tm.get_node("bed-101A").is_locked is False
    assert tm.get_node("room-101").locked_descendant_count == 0

def test_unlock_wrong_agent_failure(tm):
    tm.lock("bed-101A", "nurse-jones")
    success, msg = tm.unlock("bed-101A", "dr-smith")
    assert success is False
    assert "cannot unlock" in msg

def test_upgrade_lock_success(tm):
    tm.lock("bed-101A", "dr-smith")
    tm.lock("bed-101B", "dr-smith")

    success, msg = tm.upgrade_lock("room-101", "dr-smith")
    assert success is True

    room = tm.get_node("room-101")
    assert room.is_locked is True
    assert room.locked_by == "dr-smith"

    assert tm.get_node("bed-101A").is_locked is False
    assert tm.get_node("bed-101B").is_locked is False
