import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.tree_manager import TreeManager, create_default_hospital_tree

def test_simultaneous_same_node_lock_contention():
    """
    Spawns 20 threads that synchronize on a Barrier and simultaneously try to lock 'bed-101A'.
    Guarantees exactly ONE thread succeeds and 19 fail without race conditions.
    """
    root = create_default_hospital_tree()
    tm = TreeManager(root)

    num_threads = 20
    barrier = threading.Barrier(num_threads)
    results = []
    results_lock = threading.Lock()

    def worker(agent_idx):
        agent_id = f"nurse-{agent_idx}"
        barrier.wait()
        success, msg = tm.lock("bed-101A", agent_id, ttl_seconds=30.0)
        with results_lock:
            results.append((success, agent_id))

    threads = []
    for i in range(num_threads):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    successes = [r for r in results if r[0] is True]
    failures = [r for r in results if r[0] is False]

    assert len(successes) == 1
    assert len(failures) == num_threads - 1
    assert tm.get_node("bed-101A").is_locked is True

def test_simultaneous_overlapping_parent_child_contention():
    """
    10 threads try to lock parent 'room-101' while 10 threads try to lock child 'bed-101A'.
    Confirms thread safety and mutual exclusion between parent and child locks.
    """
    root = create_default_hospital_tree()
    tm = TreeManager(root)

    num_threads = 20
    barrier = threading.Barrier(num_threads)
    results = []
    lock = threading.Lock()

    def parent_worker(idx):
        agent_id = f"dr-{idx}"
        barrier.wait()
        res = tm.lock("room-101", agent_id)
        with lock:
            results.append(("parent", res[0]))

    def child_worker(idx):
        agent_id = f"nurse-{idx}"
        barrier.wait()
        res = tm.lock("bed-101A", agent_id)
        with lock:
            results.append(("child", res[0]))

    threads = []
    for i in range(10):
        threads.append(threading.Thread(target=parent_worker, args=(i,)))
        threads.append(threading.Thread(target=child_worker, args=(i,)))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    parent_successes = [r for r in results if r[0] == "parent" and r[1] is True]
    child_successes = [r for r in results if r[0] == "child" and r[1] is True]

    # Either 1 parent succeeded OR 1 child succeeded, but NEVER both!
    assert not (len(parent_successes) > 0 and len(child_successes) > 0)
    assert len(parent_successes) + len(child_successes) == 1

def test_high_concurrency_lock_unlock_stress():
    """
    Stress test with 50 concurrent lock/unlock tasks across various beds and rooms.
    """
    root = create_default_hospital_tree()
    tm = TreeManager(root)

    def random_task(i):
        node_id = f"bed-101A" if i % 2 == 0 else f"bed-101B"
        agent_id = f"agent-{i}"
        locked, _ = tm.lock(node_id, agent_id)
        if locked:
            tm.unlock(node_id, agent_id)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(random_task, i) for i in range(50)]
        for f in futures:
            f.result()

    # Tree counters must return to 0 after all unlocks
    assert tm.get_node("hospital-1").locked_descendant_count == 0
