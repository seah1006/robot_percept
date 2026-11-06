import threading
import time

import pytest

from web.monowait import join_thread, wait_event, wait_for, wait_until


@pytest.mark.parametrize("wall_step", [-4.9, 92.0])
def test_wait_event_uses_monotonic_deadline(monkeypatch, wall_step):
    real_wall = time.time
    monkeypatch.setattr(time, "time", lambda: real_wall() + wall_step)
    started = time.monotonic()
    assert wait_event(threading.Event(), .05, slice_s=.005) is False
    elapsed = time.monotonic() - started
    assert .04 <= elapsed < .20


def test_wait_until_returns_immediately_for_pre_set_stop():
    stop = threading.Event()
    stop.set()
    started = time.monotonic()
    assert wait_until(stop, started + 10) is True
    assert time.monotonic() - started < .02


def test_predicate_poll_does_not_add_condition_scale_latency():
    ready = {"value": False}
    worker = threading.Thread(target=lambda: (time.sleep(.02), ready.__setitem__("value", True)))
    worker.start()
    started = time.monotonic()
    assert wait_for(lambda: ready["value"], .5, slice_s=.005)
    assert time.monotonic() - started < .10
    worker.join()


def test_render_style_loop_stops_within_50ms():
    stop = threading.Event()
    exited = threading.Event()

    def loop():
        while not wait_event(stop, 1., slice_s=.01):
            pass
        exited.set()

    thread = threading.Thread(target=loop)
    thread.start()
    started = time.monotonic()
    stop.set()
    assert join_thread(thread, .05, slice_s=.005)
    assert exited.is_set()
    assert time.monotonic() - started <= .05
