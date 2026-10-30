"""Combine a minute CPU report with current system measurements."""

import os
import time

from .inventory import get_cached_inventory
from .metrics import (
  format_uptime,
  get_connections,
  get_disk,
  get_memory,
  get_load_average,
  get_network,
  get_uptime_seconds,
)
from .sampler import server_timestamp


def collect_payload(cpu_report):
  # Preserve the CPU window and its original timestamps.
  payload = dict(cpu_report)

  payload['agent_version'] = os.environ.get('LYTESCOPE_AGENT_VERSION', '0.3.0',)

  # Collect current snapshots after the CPU window ends.
  snapshot_started_at = time.time()

  payload.update(get_connections())
  payload.update(get_disk())
  payload.update(get_memory())
  payload.update(get_load_average())
  payload.update(get_network())

  uptime_seconds = get_uptime_seconds()

  if uptime_seconds is not None:
    payload['uptime'] = format_uptime(uptime_seconds)

  snapshot_finished_at = time.time()
  payload['snapshot_started_at'] = server_timestamp(snapshot_started_at,)
  payload['snapshot_finished_at'] = server_timestamp(snapshot_finished_at,)

  # External inventory lookups happen after local snapshots.
  payload.update(get_cached_inventory())

  return payload