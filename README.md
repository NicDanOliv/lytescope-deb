# Lytescope Linux Agent

The Lytescope Linux Agent is a lightweight server monitoring agent for Linux servers.

It collects basic system metrics and sends them to Lytescope so the server can be monitored from the Lytescope dashboard.

## What it collects

The agent collects system-level metrics such as:

- Hostname
- OS information
- Kernel version
- CPU load and usage
- Memory usage
- Disk usage
- Network interface data
- Local IP address
- Public IP address
- Uptime
- TCP connection count

## What it installs

The Debian package installs:

```text
/usr/local/bin/lytescope
/usr/local/lib/lytescope/build_payload.py
/etc/lytescope/agent.conf
/etc/systemd/system/lytescope.service
/etc/systemd/system/lytescope.timer