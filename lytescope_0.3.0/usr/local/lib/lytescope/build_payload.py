#!/usr/bin/env python3

"""Collect minute reports, with optional API delivery."""

import argparse
import json
import sys

from lytescope_agent.collector import collect_payload
from lytescope_agent.config import CONFIG_FILE, load_config
from lytescope_agent.runtime import SamplingService
from lytescope_agent.transport import (
  monitoring_enabled,
  send_metrics,
)


def diagnostic(message):
  print(
    f'Lytescope: {message}',
    file=sys.stderr,
    flush=True,
  )


def main(argv=None):
  parser = argparse.ArgumentParser(
    description='Collect minute-average CPU reports.',
  )

  parser.add_argument(
    '--reports',
    type=int,
    default=1,
    help='Number of intervals to process; 0 runs continuously.',
  )

  parser.add_argument(
    '--upload',
    action='store_true',
    help='Send reports to the configured API.',
  )

  parser.add_argument(
    '--config',
    default=CONFIG_FILE,
    help='Configuration file used for uploads.',
  )

  args = parser.parse_args(argv)

  if args.reports < 0:
    parser.error('--reports must be zero or greater')

  processed = 0
  delivered = 0
  delivery_failed = False

  try:
    config = load_config(args.config) if args.upload else None

    with SamplingService() as service:
      while args.reports == 0 or processed < args.reports:
        cpu_report = service.get_report()

        if cpu_report is None:
          raise RuntimeError('Sampling stopped unexpectedly')

        processed += 1

        if not args.upload:
          payload = collect_payload(cpu_report)

          print(
            json.dumps(payload, separators=(',', ':')),
            flush=True,
          )

          continue

        try:
          if not monitoring_enabled(config):
            diagnostic('Monitoring disabled; report skipped.')
            continue

          payload = collect_payload(cpu_report)
          payload['agent_version'] = (
            config['LYTESCOPE_AGENT_VERSION']
          )

          send_metrics(payload, config)
          delivered += 1

          diagnostic(
            f'Report delivered: {payload["server_time"]}'
          )
        except (RuntimeError, ValueError, OSError) as error:
          delivery_failed = True
          diagnostic(f'Report delivery failed: {error}')

  except KeyboardInterrupt:
    return 130
  except (RuntimeError, ValueError, OSError) as error:
    diagnostic(str(error))
    return 1

  if delivery_failed:
    return 1

  if args.upload and delivered == 0:
    return 3

  return 0


if __name__ == '__main__':
  sys.exit(main())