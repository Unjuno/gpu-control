#!/usr/bin/env python3
"""Poll capacity journal events into the private durable bridge outbox.

This process does not deliver notifications. Bootstrap is an explicit
operator action; timer invocations only resume from an existing checkpoint.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Callable, Sequence

from capacity_event_state import (
    CapacityEventError,
    CapacityEventState,
    JournalCheckpointStillRetained,
    JournalPoller,
    JournalRetentionGap,
    JournalStateUninitialized,
    JournalctlSource,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--bootstrap-latest", action="store_true",
                        help="explicitly establish the latest retained event as baseline")
    action.add_argument("--poll-once", action="store_true",
                        help="resume from the existing journal cursor and exit")
    action.add_argument("--reconcile-latest", action="store_true",
                        help="after a retention gap, explicitly rebase to the latest status")
    action.add_argument("--show-health", action="store_true",
                        help="print redacted local outbox counters without reading journald")
    parser.add_argument("--state-path", type=Path, required=True,
                        help="operator-owned private bridge state file")
    return parser


def main(argv: Sequence[str] | None = None, *,
         source_factory: Callable[[], JournalctlSource] = JournalctlSource,
         state_factory: Callable[[Path], CapacityEventState] = CapacityEventState) -> int:
    args = _parser().parse_args(argv)
    state = state_factory(args.state_path)
    reconciled = False
    reconciled_status = None
    try:
        if args.show_health:
            processed = []
        else:
            poller = JournalPoller(source_factory(), state)
            if args.bootstrap_latest:
                processed = poller.bootstrap_latest()
            elif args.reconcile_latest:
                result = poller.reconcile_latest()
                processed = [result]
                reconciled = True
                reconciled_status = result.current_status
            else:
                processed = poller.poll_once()
        health = state.delivery_health()
    except JournalCheckpointStillRetained:
        print("capacity_bridge_result=normal_poll_required reason=checkpoint_retained",
              file=sys.stderr)
        return 2
    except JournalRetentionGap:
        print("capacity_bridge_result=unknown_state reason=journal_retention_gap",
              file=sys.stderr)
        return 3
    except JournalStateUninitialized:
        print("capacity_bridge_result=bootstrap_required", file=sys.stderr)
        return 4
    except CapacityEventError:
        print("capacity_bridge_result=journal_or_state_error", file=sys.stderr)
        return 1
    except OSError:
        print("capacity_bridge_result=state_io_error", file=sys.stderr)
        return 1

    print(json.dumps({"processed": len(processed), "reconciled": reconciled,
                      "reconciled_status": reconciled_status, "health": health},
                     sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
