"""Collect CPU averages at 60-second intervals."""

import time
from datetime import datetime

from .metrics import calculate_cpu_sample, read_cpu_stats


INTERVAL_SECONDS = 60
TIMING_TOLERANCE = 0.5


class SamplingStopped(Exception):
  """Raised when the collector is stopped."""


def pause(seconds, stop_event=None):
  if stop_event is None:
    time.sleep(seconds)
  elif stop_event.wait(seconds):
    raise SamplingStopped()


def server_timestamp(timestamp):
  return datetime.fromtimestamp(
    timestamp,
  ).astimezone().isoformat(timespec='milliseconds')


def read_sample():
  monotonic = time.monotonic()
  wall = time.time()
  counters = read_cpu_stats()

  return counters, wall, monotonic


def make_report(first, second):
  first_counters, first_wall, first_monotonic = first
  second_counters, second_wall, second_monotonic = second

  elapsed = second_monotonic - first_monotonic

  clock_difference = (
    second_wall - first_wall - elapsed
  )

  sample = calculate_cpu_sample(
    first_counters,
    second_counters,
  )

  valid = sample is not None and elapsed > 0

  return {
    'sampled_at': int(second_wall),
    'server_time': server_timestamp(second_wall),
    'window_start': server_timestamp(first_wall),
    'window_end': server_timestamp(second_wall),
    'window_seconds': INTERVAL_SECONDS,
    'measurement_start': server_timestamp(first_wall),
    'measurement_end': server_timestamp(second_wall),
    'measurement_seconds': round(elapsed, 3),
    'cpu_used_perc': (
      round(sample['cpu_used_perc'], 2)
      if valid
      else None
    ),
    'cpu_iowait_perc': (
      round(sample['cpu_iowait_perc'], 2)
      if valid
      else None
    ),
    'cpu_measurement_valid_yn': valid,
    'cpu_invalid_reason': (
      None if valid else 'counters_unavailable'
    ),
    'clock_adjusted_yn': (
      abs(clock_difference) > TIMING_TOLERANCE
    ),
    'sampling_delayed_yn': (
      abs(elapsed - INTERVAL_SECONDS) > TIMING_TOLERANCE
    ),
  }


def sample_minutes(stop_event=None):
  first = read_sample()
  deadline = first[2] + INTERVAL_SECONDS

  while True:
    if stop_event is not None and stop_event.is_set():
      raise SamplingStopped()

    while True:
      remaining = deadline - time.monotonic()

      if remaining <= 0:
        break

      pause(remaining, stop_event)

    second = read_sample()
    report = make_report(first, second)

    # Reuse the ending counters as the next starting counters.
    first = second
    deadline += INTERVAL_SECONDS

    # After a long interruption, resume a normal interval
    # rather than generating immediate catch-up reports.
    if deadline <= second[2]:
      deadline = second[2] + INTERVAL_SECONDS

    yield report