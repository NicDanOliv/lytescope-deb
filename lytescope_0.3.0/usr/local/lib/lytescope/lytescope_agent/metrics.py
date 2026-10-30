"""Read CPU, memory, disk, network, connections, and uptime."""

import time

from .system import read_file, run_command, safe_float, safe_int

# ==================== UPTIME ==================== #
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
    parts.append(
      f"{days} day" + ("" if days == 1 else "s")
    )

  if hours > 0:
    parts.append(
      f"{hours} hour" + ("" if hours == 1 else "s")
    )

  if minutes > 0 or not parts:
    parts.append(
      f"{minutes} minute" + ("" if minutes == 1 else "s")
    )

  return ", ".join(parts)
# ==================== UPTIME ==================== #

# ==================== CONNECTIONS ==================== #
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
    'connections': (
      count_tcp_connections_from_file('/proc/net/tcp')
      + count_tcp_connections_from_file('/proc/net/tcp6')
    ),
  }
# ==================== CONNECTIONS ==================== #

# ==================== DISK ==================== #
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

  if (
    total_bytes is None
    or used_bytes is None
    or free_bytes is None
  ):
    return {}

  return {
    'disk_total': round(total_bytes / 1024 / 1024, 2),
    'disk_free': round(free_bytes / 1024 / 1024, 2),
    'disk_used': round(used_bytes / 1024 / 1024, 2),
  }
# ==================== DISK ==================== #

# ==================== MEMORY ==================== #
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
# ==================== MEMORY ==================== #

# ==================== CPU ==================== #
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
  """Read cumulative CPU counters across all processors."""

  fields = (
    'user',
    'nice',
    'system',
    'idle',
    'iowait',
    'irq',
    'softirq',
    'steal',
  )

  for line in read_file('/proc/stat').splitlines():
    if not line.startswith('cpu '):
      continue

    parts = line.split()[1:]

    if len(parts) < len(fields):
      return None

    try:
      counters = {
        field: int(parts[index])
        for index, field in enumerate(fields)
      }
    except ValueError:
      return None

    if any(value < 0 for value in counters.values()):
      return None

    return counters

  return None

def calculate_cpu_sample(first, second):
  """Calculate usage and counter changes between two readings."""

  if first is None or second is None:
    return None

  fields = (
    'user',
    'nice',
    'system',
    'idle',
    'iowait',
    'irq',
    'softirq',
    'steal',
  )

  if any(
    field not in first or field not in second
    for field in fields
  ):
    return None

  changes = {
    field: second[field] - first[field]
    for field in fields
  }

  # Counter resets or decreases cannot produce a reliable sample.
  if any(value < 0 for value in changes.values()):
    return None

  total_ticks = sum(changes.values())

  if total_ticks <= 0:
    return None

  idle_ticks = changes['idle'] + changes['iowait']
  busy_ticks = total_ticks - idle_ticks

  return {
    'total_ticks': total_ticks,
    'busy_ticks': busy_ticks,
    'iowait_ticks': changes['iowait'],
    'cpu_used_perc': busy_ticks / total_ticks * 100,
    'cpu_iowait_perc': changes['iowait'] / total_ticks * 100,
  }

def get_cpu_usage():
  """Preserve the existing one-second collection entry point."""

  first = read_cpu_stats()
  time.sleep(1)
  second = read_cpu_stats()

  sample = calculate_cpu_sample(first, second)

  if sample is None:
    return {}

  return {
    'cpu_used_perc': round(sample['cpu_used_perc'], 2),
    'cpu_iowait_perc': round(sample['cpu_iowait_perc'], 2),
  }
# ==================== CPU ==================== #

# ==================== NETWORK ==================== #
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

    _, values = line.split(':', 1)
    parts = values.split()

    if len(parts) < 16:
      return result

    rx_bytes = safe_float(parts[0]) or 0
    tx_bytes = safe_float(parts[8]) or 0

    result['received_data'] = round(
      rx_bytes / 1024 / 1024,
      2,
    )

    result['sent_data'] = round(
      tx_bytes / 1024 / 1024,
      2,
    )

    return result

  return result
# ==================== NETWORK ==================== #
