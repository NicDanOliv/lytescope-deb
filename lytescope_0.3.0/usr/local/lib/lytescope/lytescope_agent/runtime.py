"""Keep minute CPU sampling independent of report handling."""

import queue
import sys
import threading

from .sampler import SamplingStopped, sample_minutes


class SamplingService:
  def __init__(self, queue_size=5):
    if queue_size < 1:
      raise ValueError('queue_size must be at least 1')

    self.reports = queue.Queue(maxsize=queue_size)
    self.stop_event = threading.Event()

    self.error = None
    self.dropped_reports = 0

    self.thread = threading.Thread(
      target=self._run,
      name='lytescope-minute-sampler',
      daemon=True,
    )

  def _enqueue(self, report):
    try:
      self.reports.put_nowait(report)
      return
    except queue.Full:
      pass

    try:
      self.reports.get_nowait()
      self.dropped_reports += 1

      print(
        'Lytescope: report queue full; oldest report dropped.',
        file=sys.stderr,
        flush=True,
      )
    except queue.Empty:
      pass

    self.reports.put_nowait(report)

  def _run(self):
    try:
      for report in sample_minutes(self.stop_event):
        if self.stop_event.is_set():
          break

        self._enqueue(report)
    except SamplingStopped:
      pass
    except Exception as error:
      self.error = error
    finally:
      self.stop_event.set()

  def get_report(self):
    while True:
      if self.error is not None:
        raise RuntimeError(
          'CPU sampling failed'
        ) from self.error

      try:
        return self.reports.get(timeout=0.25)
      except queue.Empty:
        if self.stop_event.is_set():
          return None

  def stop(self):
    self.stop_event.set()
    self.thread.join(timeout=2)

  def __enter__(self):
    self.thread.start()
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    self.stop()