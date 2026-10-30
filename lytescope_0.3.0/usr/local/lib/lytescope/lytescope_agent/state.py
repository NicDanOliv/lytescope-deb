"""Load and save the persistent inventory cache."""

import json
import os
import tempfile


INVENTORY_CACHE_DIRECTORY = '/var/lib/lytescope'
INVENTORY_CACHE_FILE = (
  INVENTORY_CACHE_DIRECTORY + '/inventory_cache.json'
)


def load_inventory_cache():
  try:
    with open(INVENTORY_CACHE_FILE, 'r') as file:
      cache = json.load(file)

    if isinstance(cache, dict):
      return cache
  except Exception:
    pass

  return {}


def save_inventory_cache(cache):
  temporary_path = None

  try:
    os.makedirs(
      INVENTORY_CACHE_DIRECTORY,
      mode=0o700,
      exist_ok=True,
    )

    os.chmod(INVENTORY_CACHE_DIRECTORY, 0o700)

    file_descriptor, temporary_path = tempfile.mkstemp(
      prefix='inventory_cache.',
      dir=INVENTORY_CACHE_DIRECTORY,
    )

    with os.fdopen(file_descriptor, 'w') as file:
      json.dump(cache, file, separators=(',', ':'))

    os.chmod(temporary_path, 0o600)
    os.replace(temporary_path, INVENTORY_CACHE_FILE)
  except Exception:
    if temporary_path and os.path.exists(temporary_path):
      os.remove(temporary_path)