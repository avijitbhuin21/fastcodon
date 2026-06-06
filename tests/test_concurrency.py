# P33 structured-concurrency leaf — TaskGroup join, deadline cancellation, and Event, all driven
# by ONE Reactor.run_forever(). A watchdog Timeout stops the reactor after a few seconds so a bug
# can never hang CI. No sockets: sleep(r, delay) is the canonical async "task".

from time import monotonic
from fastcodon.reactor import Reactor, TimerCallback
from fastcodon.aio.streams import Completion, Continuation
from fastcodon.aio.timeout import Timeout, TimeoutAction
from fastcodon.aio.sleep import sleep
from fastcodon.aio.scope import CancelScope
from fastcodon.aio.taskgroup import TaskGroup
from fastcodon.aio.sync import Event


# ---- watchdog: hard stop so a bug can't hang CI -------------------------------------------
class StopReactor(TimeoutAction):
    r: Reactor
    fired: List[bool]
    def __init__(self, r: Reactor, fired: List[bool]):
        self.r = r
        self.fired = fired
    def run(self):
        print("WATCHDOG fired (timeout) — stopping reactor")
        self.fired[0] = True
        self.r.stop()


# ---- a poller TimerCallback that re-arms itself until all scenarios are settled, then stops --
class Poller(TimerCallback):
    r: Reactor
    tg: TaskGroup
    guard_scope: CancelScope
    guarded: Completion
    waiter: Completion
    def __init__(self, r: Reactor, tg: TaskGroup, guard_scope: CancelScope,
                 guarded: Completion, waiter: Completion):
        self.r = r
        self.tg = tg
        self.guard_scope = guard_scope
        self.guarded = guarded
        self.waiter = waiter
    def run(self):
        if self.tg.done and self.guarded.done and self.waiter.done:
            self.r.stop()
        else:
            self.r.call_later(0.005, self)   # re-arm


# ---- Event waiter records that its continuation actually ran ------------------------------
class OnEvent(Continuation):
    ran: List[bool]
    err: List[bool]
    def __init__(self, ran: List[bool], err: List[bool]):
        super().__init__()
        self.ran = ran
        self.err = err
    def run(self):
        self.ran[0] = True
        self.err[0] = self.errored


class FireEvent(TimerCallback):
    ev: Event
    def __init__(self, ev: Event):
        self.ev = ev
    def run(self):
        self.ev.set()


def main():
    r = Reactor()
    wd_fired = [False]
    watchdog = Timeout(r, 4.0, StopReactor(r, wd_fired)).start()

    t0 = monotonic()

    # --- scenario 1: TaskGroup join (3 sleeps of differing short delays) ---
    tg = TaskGroup(r)
    tg.open()
    s1 = tg.start(sleep(r, 0.02))
    s2 = tg.start(sleep(r, 0.05))
    s3 = tg.start(sleep(r, 0.08))

    # --- scenario 2: deadline cancellation (0.05s deadline guarding a 1.0s sleep) ---
    guarded = sleep(r, 1.0)
    guard_scope = CancelScope(r, deadline=0.05)
    guard_scope.open()
    guard_scope.add(guarded)

    # --- scenario 3: Event — waiter parks, a timer set()s it after 0.05s ---
    ev = Event()
    ran = [False]
    everr = [False]
    waiter = ev.wait()
    waiter.then(OnEvent(ran, everr))
    r.call_later(0.05, FireEvent(ev))

    # poller drives shutdown once everything settles
    r.call_later(0.005, Poller(r, tg, guard_scope, guarded, waiter))

    r.run_forever()
    elapsed = monotonic() - t0
    watchdog.done()
    tg.close()
    guard_scope.close()

    assert not wd_fired[0], "watchdog fired — something hung / did not settle"

    # scenario 1 assertions
    assert tg.all_done() and tg.done, "task group did not report done"
    assert not tg.any_errored(), "no task should have errored"
    assert s1.done and not s1.errored, "task 1 should be done, not errored"
    assert s2.done and not s2.errored, "task 2 should be done, not errored"
    assert s3.done and not s3.errored, "task 3 should be done, not errored"
    print("taskgroup: 3 tasks joined, none errored")

    # scenario 2 assertions
    assert guarded.done and guarded.errored, "guarded sleep should be cancelled (errored)"
    assert guard_scope.cancelled, "scope should report cancelled"
    assert guard_scope.deadline_expired, "the deadline (not a manual cancel) should have fired"
    assert elapsed < 0.9, "cancellation must happen well before the 1.0s sleep (got " + str(elapsed) + "s)"
    print("cancelscope: deadline fired and cancelled guarded sleep in", round(elapsed, 3), "s")

    # scenario 3 assertions
    assert waiter.done and not waiter.errored, "event waiter should be done, not errored"
    assert ran[0] and not everr[0], "event continuation should have run without error"
    print("event: waiter continuation ran after set()")

    r.close()
    print("PASS: structured concurrency (taskgroup/cancelscope/event) ok")

main()
