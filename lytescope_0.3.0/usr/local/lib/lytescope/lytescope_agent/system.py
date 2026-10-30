"""Shared helpers for numbers, files, and system commands."""

import subprocess


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
    text=True,
  )

  return result.stdout.strip()


def read_file(path):
  try:
    with open(path, 'r') as file:
      return file.read()
  except Exception:
    return ''