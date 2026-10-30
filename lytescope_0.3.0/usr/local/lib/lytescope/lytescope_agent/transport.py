"""Sign API requests and deliver metric reports."""

import hashlib
import hmac
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import (
  HTTPRedirectHandler,
  Request,
  build_opener,
)


REQUEST_TIMEOUT = 20


class NoRedirects(HTTPRedirectHandler):
  def redirect_request(self, *args, **kwargs):
    return None


def signed_request(method, endpoint, config, payload=None):
  url = urlsplit(endpoint)

  if (
    not url.hostname
    or url.username is not None
    or url.password is not None
    or url.fragment
  ):
    raise ValueError('Invalid API endpoint')

  local_hosts = ('localhost', '127.0.0.1', '::1')

  if url.scheme != 'https':
    if url.scheme != 'http' or url.hostname not in local_hosts:
      raise ValueError(
        'API endpoint must use HTTPS, except on localhost'
      )

  body = b''

  if payload is not None:
    body = json.dumps(
      payload,
      separators=(',', ':'),
      allow_nan=False,
    ).encode('utf-8')

  timestamp = str(int(time.time()))
  path = url.path or '/'

  if url.query:
    path += '?' + url.query

  canonical_request = '\n'.join((
    timestamp,
    method,
    path,
    hashlib.sha256(body).hexdigest(),
  ))

  signature = hmac.new(
    config['LYTESCOPE_AGENT_SIGNING_SECRET'].encode('utf-8'),
    canonical_request.encode('utf-8'),
    hashlib.sha256,
  ).hexdigest()

  headers = {
    'Accept': 'application/json',
    'X-Lytescope-Agent': config['LYTESCOPE_AGENT_UUID'],
    'X-Lytescope-Timestamp': timestamp,
    'X-Lytescope-Signature': signature,
    'X-Lytescope-Signature-Version': config.get(
      'LYTESCOPE_AGENT_SIGNATURE_VERSION',
      'v1',
    ),
  }

  if payload is not None:
    headers['Content-Type'] = 'application/json'

  return Request(
    endpoint,
    data=body if payload is not None else None,
    method=method,
    headers=headers,
  )


def prepare_request(payload, config):
  return signed_request(
    'POST',
    config['LYTESCOPE_ENDPOINT'],
    config,
    payload,
  )


def prepare_status_request(config):
  return signed_request(
    'GET',
    config['LYTESCOPE_STATUS_ENDPOINT'],
    config,
  )


def send_request(request):
  opener = build_opener(NoRedirects())

  try:
    with opener.open(
      request,
      timeout=REQUEST_TIMEOUT,
    ) as response:
      return response.read().decode('utf-8')
  except HTTPError as error:
    status = error.code
    error.close()

    raise RuntimeError(
      f'API returned HTTP {status}'
    ) from error
  except (URLError, TimeoutError, OSError) as error:
    raise RuntimeError(
      'Could not connect to the API'
    ) from error


def monitoring_enabled(config):
  response = send_request(prepare_status_request(config))

  try:
    status = json.loads(response)
  except ValueError as error:
    raise RuntimeError(
      'Monitoring status response is not valid JSON'
    ) from error

  if not isinstance(status, dict):
    raise RuntimeError('Invalid monitoring status response')

  enabled = status.get('monitor_active_yn')

  if not isinstance(enabled, bool):
    raise RuntimeError(
      'Monitoring status must contain monitor_active_yn '
      'as true or false'
    )

  return enabled


def send_metrics(payload, config):
  return send_request(prepare_request(payload, config))