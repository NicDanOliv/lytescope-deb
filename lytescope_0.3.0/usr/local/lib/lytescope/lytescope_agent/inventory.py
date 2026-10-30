"""Collect server identity and manage inventory cache freshness."""

import os
import platform
import socket
import time

from pathlib import Path
from .state import load_inventory_cache, save_inventory_cache
from .system import read_file, run_command


PUBLIC_IP_CACHE_SECONDS = 900
STATIC_INVENTORY_CACHE_SECONDS = 900


def get_os_info():
  data = read_file('/etc/os-release')
  values = {}

  for line in data.splitlines():
    if '=' not in line:
      continue

    key, value = line.split('=', 1)
    values[key] = value.strip().strip('"')

  return {
    'os_info': values.get('PRETTY_NAME') or platform.platform(),
    'kernel_version': platform.release(),
    'architecture': platform.machine(),
  }


def get_threads():
  count = os.cpu_count()

  if count is None:
    return {}

  return {
    'threads': count,
  }


def get_public_ip():
  output = run_command(
    'curl -fsS --max-time 3 https://api.ipify.org'
  )

  if not output:
    return None

  return output


def get_cached_inventory():
  cache = load_inventory_cache()
  inventory = {}
  cache_changed = False

  current_time = time.time()

  static_inventory = cache.get('static_inventory')
  static_inventory_updated_at = cache.get(
    'static_inventory_updated_at'
  )

  static_inventory_fresh_yn = (
    isinstance(static_inventory, dict)
    and isinstance(static_inventory_updated_at, (int, float))
    and (
      0 <= current_time - static_inventory_updated_at
      < STATIC_INVENTORY_CACHE_SECONDS
    )
  )

  if not static_inventory_fresh_yn:
    static_inventory = {
      'hostname': socket.gethostname(),
    }

    static_inventory.update(get_os_info())
    static_inventory.update(get_threads())

    cache['static_inventory'] = static_inventory
    cache['static_inventory_updated_at'] = int(current_time)
    cache_changed = True

  inventory.update(static_inventory)
  inventory['timezone'] = get_timezone()

  cached_public_ip = cache.get('public_ip')
  public_ip_updated_at = cache.get('public_ip_updated_at')

  public_ip_fresh_yn = (
    isinstance(public_ip_updated_at, (int, float))
    and (
      0 <= current_time - public_ip_updated_at
      < PUBLIC_IP_CACHE_SECONDS
    )
  )

  if not cached_public_ip or not public_ip_fresh_yn:
    public_ip = get_public_ip()

    if public_ip:
      cached_public_ip = public_ip
      cache['public_ip'] = public_ip
      cache['public_ip_updated_at'] = int(time.time())
      cache_changed = True

  if cached_public_ip:
    inventory['public_ip'] = cached_public_ip

  if cache_changed:
    save_inventory_cache(cache)

  return inventory

def get_timezone():
  timezone = os.environ.get('TZ', '').lstrip(':')

  if timezone and not timezone.startswith('/'):
    return timezone

  localtime = Path('/etc/localtime').resolve()
  marker = '/zoneinfo/'

  if marker in str(localtime):
    return str(localtime).split(marker, 1)[1]

  timezone_file = Path('/etc/timezone')

  try:
    timezone = timezone_file.read_text().strip()

    if timezone:
      return timezone
  except OSError:
    pass

  return None