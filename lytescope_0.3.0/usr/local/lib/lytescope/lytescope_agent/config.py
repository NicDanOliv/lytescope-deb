"""Read the existing linked-agent configuration."""

import json
import subprocess
import sys
from pathlib import Path


CONFIG_FILE = '/etc/lytescope/agent.conf'
VERSION_FILE = '/usr/local/lib/lytescope/version'

CONFIG_FIELDS = (
  'LYTESCOPE_BASE_URL',
  'LYTESCOPE_AGENT_UUID',
  'LYTESCOPE_AGENT_SIGNING_SECRET',
  'LYTESCOPE_ENDPOINT',
  'LYTESCOPE_STATUS_ENDPOINT',
  'LYTESCOPE_AGENT_SIGNATURE_VERSION',
  'LYTESCOPE_AGENT_VERSION',
)


def load_config(
  config_file=CONFIG_FILE,
  version_file=VERSION_FILE,
):
  if not Path(config_file).is_file():
    raise RuntimeError('Agent configuration was not found')

  export_code = (
    'import json, os; '
    f'fields = {CONFIG_FIELDS!r}; '
    'print(json.dumps({'
    'key: os.environ.get(key, "") for key in fields'
    '}))'
  )

  try:
    result = subprocess.run(
      [
        'bash',
        '-c',
        'set -ea\nsource "$1"\nexec "$2" -c "$3"',
        'lytescope-config',
        str(config_file),
        sys.executable,
        export_code,
      ],
      check=True,
      capture_output=True,
      text=True,
      timeout=5,
    )

    config = json.loads(result.stdout)
  except (
    subprocess.SubprocessError,
    OSError,
    ValueError,
  ) as error:
    raise RuntimeError(
      'Could not read agent configuration'
    ) from error

  if not isinstance(config, dict):
    raise RuntimeError('Invalid agent configuration')

  if not config['LYTESCOPE_STATUS_ENDPOINT']:
    base_url = config['LYTESCOPE_BASE_URL'].rstrip('/')

    if base_url:
      config['LYTESCOPE_STATUS_ENDPOINT'] = (
        base_url + '/api/agent/status'
      )

  config['LYTESCOPE_AGENT_SIGNATURE_VERSION'] = (
    config['LYTESCOPE_AGENT_SIGNATURE_VERSION'] or 'v1'
  )

  required_fields = (
    'LYTESCOPE_AGENT_UUID',
    'LYTESCOPE_AGENT_SIGNING_SECRET',
    'LYTESCOPE_ENDPOINT',
    'LYTESCOPE_STATUS_ENDPOINT',
  )

  if any(not config[field] for field in required_fields):
    raise RuntimeError(
      'Agent is not linked. Run: sudo lytescope link SHARE_CODE'
    )

  version_path = Path(version_file)

  if version_path.is_file():
    config['LYTESCOPE_AGENT_VERSION'] = (
      version_path.read_text().strip()
    )
  else:
    config['LYTESCOPE_AGENT_VERSION'] = (
      config['LYTESCOPE_AGENT_VERSION'] or 'unknown'
    )

  return config