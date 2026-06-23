#!/usr/bin/env python3

import json
import os
import platform
import socket
import subprocess
import time
import tempfile

INVENTORY_CACHE_DIRECTORY = '/var/lib/lytescope'
INVENTORY_CACHE_FILE = INVENTORY_CACHE_DIRECTORY + '/inventory_cache.json'
PUBLIC_IP_CACHE_SECONDS = 900

def safe_float(value):
  try:
    return float(value)
  except Exception:
    return None


def safe_int(value):
  try:
    return int(float(value))
  except Exception:
    return None


def run_command(command):
  result = subprocess.run(
    command,
    shell=True,
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
  )

  return result.stdout.strip()


def read_file(path):
  try:
    with open(path, 'r') as file:
      return file.read()
  except Exception:
    return ''


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


def get_uptime_seconds():
  values = read_file('/proc/uptime').split()

  if not values:
    return None

  return safe_int(values[0])


def format_uptime(seconds):
  seconds = safe_int(seconds)

  if seconds is None:
    return None

  days = seconds // 86400
  seconds %= 86400
  hours = seconds // 3600
  seconds %= 3600
  minutes = seconds // 60

  parts = []

  if days > 0:
    parts.append(f"{days} day" + ("" if days == 1 else "s"))

  if hours > 0:
    parts.append(f"{hours} hour" + ("" if hours == 1 else "s"))

  if minutes > 0 or not parts:
    parts.append(f"{minutes} minute" + ("" if minutes == 1 else "s"))

  return ", ".join(parts)


def get_load_average():
  values = read_file('/proc/loadavg').split()

  if len(values) < 3:
    return {}

  return {
    'cpu_load_1m': safe_float(values[0]),
    'cpu_load_5m': safe_float(values[1]),
    'cpu_load_15m': safe_float(values[2]),
  }


def read_cpu_stats():
  for line in read_file('/proc/stat').splitlines():
    if not line.startswith('cpu '):
      continue

    parts = line.split()

    return {
      'user': safe_int(parts[1]) or 0,
      'nice': safe_int(parts[2]) or 0,
      'system': safe_int(parts[3]) or 0,
      'idle': safe_int(parts[4]) or 0,
      'iowait': safe_int(parts[5]) or 0,
      'irq': safe_int(parts[6]) or 0,
      'softirq': safe_int(parts[7]) or 0,
      'steal': safe_int(parts[8]) if len(parts) > 8 else 0,
    }

  return None


def get_cpu_usage():
  first = read_cpu_stats()
  time.sleep(1)
  second = read_cpu_stats()

  if not first or not second:
    return {}

  first_idle = first['idle'] + first['iowait']
  second_idle = second['idle'] + second['iowait']
  first_total = sum(first.values())
  second_total = sum(second.values())

  total_delta = second_total - first_total
  idle_delta = second_idle - first_idle
  iowait_delta = second['iowait'] - first['iowait']

  if total_delta <= 0:
    return {}

  return {
    'cpu_used_perc': round(((total_delta - idle_delta) / total_delta) * 100, 2),
    'cpu_iowait_perc': round((iowait_delta / total_delta) * 100, 2),
  }


def get_memory():
  values = {}

  for line in read_file('/proc/meminfo').splitlines():
    parts = line.replace(':', '').split()

    if len(parts) < 2:
      continue

    values[parts[0]] = safe_float(parts[1])

  total_kb = values.get('MemTotal')
  available_kb = values.get('MemAvailable')

  if total_kb is None or available_kb is None:
    return {}

  used_kb = total_kb - available_kb

  return {
    'memory_total': round(total_kb / 1024, 2),
    'memory_free': round(available_kb / 1024, 2),
    'memory_used': round(used_kb / 1024, 2),
  }


def get_disk():
  output = run_command('df -P -B1 /')
  lines = output.splitlines()

  if len(lines) < 2:
    return {}

  parts = lines[1].split()

  if len(parts) < 6:
    return {}

  total_bytes = safe_float(parts[1])
  used_bytes = safe_float(parts[2])
  free_bytes = safe_float(parts[3])

  if total_bytes is None or used_bytes is None or free_bytes is None:
    return {}

  return {
    'disk_total': round(total_bytes / 1024 / 1024, 2),
    'disk_free': round(free_bytes / 1024 / 1024, 2),
    'disk_used': round(used_bytes / 1024 / 1024, 2),
  }


def get_default_route():
  output = run_command('ip route get 1.1.1.1')
  parts = output.split()

  route = {
    'network_interface': None,
    'local_ip': None,
  }

  for index, value in enumerate(parts):
    if value == 'dev' and index + 1 < len(parts):
      route['network_interface'] = parts[index + 1]

    if value == 'src' and index + 1 < len(parts):
      route['local_ip'] = parts[index + 1]

  return route


def get_network():
  route = get_default_route()
  interface = route.get('network_interface')
  data = read_file('/proc/net/dev')

  result = {
    'local_ip': route.get('local_ip'),
  }

  if not interface:
    return result

  for line in data.splitlines():
    line = line.strip()

    if not line.startswith(interface + ':'):
      continue

    name, values = line.split(':', 1)
    parts = values.split()

    if len(parts) < 16:
      return result

    rx_bytes = safe_float(parts[0]) or 0
    tx_bytes = safe_float(parts[8]) or 0

    result['received_data'] = round(rx_bytes / 1024 / 1024, 2)
    result['sent_data'] = round(tx_bytes / 1024 / 1024, 2)

    return result

  return result


def get_public_ip():
  output = run_command('curl -fsS --max-time 3 https://api.ipify.org')

  if not output:
    return None

  return output

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
    os.makedirs(INVENTORY_CACHE_DIRECTORY, mode=0o700, exist_ok=True)
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


def get_cached_inventory():
  cache = load_inventory_cache()
  inventory = {}
  cache_changed = False

  static_inventory = cache.get('static_inventory')

  if not isinstance(static_inventory, dict):
    static_inventory = {
      'hostname': socket.gethostname(),
    }

    static_inventory.update(get_os_info())
    static_inventory.update(get_threads())

    cache['static_inventory'] = static_inventory
    cache['static_inventory_updated_at'] = int(time.time())
    cache_changed = True

  inventory.update(static_inventory)

  cached_public_ip = cache.get('public_ip')
  public_ip_updated_at = cache.get('public_ip_updated_at')
  public_ip_fresh_yn = (
    isinstance(public_ip_updated_at, (int, float))
    and (time.time() - public_ip_updated_at) < PUBLIC_IP_CACHE_SECONDS
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

def count_tcp_connections_from_file(path):
  count = 0

  for index, line in enumerate(read_file(path).splitlines()):
    if index == 0:
      continue

    parts = line.split()

    if len(parts) < 4:
      continue

    if parts[3] == '01':
      count += 1

  return count


def get_connections():
  return {
    'connections': count_tcp_connections_from_file('/proc/net/tcp') + count_tcp_connections_from_file('/proc/net/tcp6'),
  }


payload = {
  'agent_version': os.environ.get('LYTESCOPE_AGENT_VERSION', '0.1.0'),
  'sampled_at': int(time.time()),
  'server_time': time.strftime('%Y-%m-%d %H:%M:%S'),
}

payload.update(get_cached_inventory())
payload.update(get_load_average())
payload.update(get_cpu_usage())
payload.update(get_memory())
payload.update(get_disk())
payload.update(get_network())
payload.update(get_connections())

uptime_seconds = get_uptime_seconds()

if uptime_seconds is not None:
  payload['uptime'] = format_uptime(uptime_seconds)

print(json.dumps(payload, separators=(',', ':')))