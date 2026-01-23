# Asterisk Grafana Cloud Monitoring Integration

This document describes the Grafana/Prometheus/Loki monitoring integration that was installed for Asterisk and provides instructions for replicating it on other machines.

## Overview

The integration sends Asterisk metrics and logs to a remote monitoring server using Grafana Alloy (formerly Grafana Agent). This enables centralized monitoring, alerting, and visualization of Asterisk PBX systems.

## Architecture

```
┌─────────────────────────────────────────────┐
│ Asterisk Server (node592420)               │
│                                             │
│  ┌──────────────┐                          │
│  │  Asterisk    │                          │
│  │  PBX         │                          │
│  └──────┬───────┘                          │
│         │                                   │
│         ├─► HTTP Server (port 8088)        │
│         │   └─► /metrics (Prometheus)      │
│         │                                   │
│         └─► Logs (/var/log/asterisk/full) │
│                                             │
│  ┌──────────────┐                          │
│  │ Grafana      │                          │
│  │ Alloy        │                          │
│  │              │                          │
│  │ - Scrapes    │                          │
│  │   metrics    │                          │
│  │ - Tails      │                          │
│  │   logs       │                          │
│  │ - Exports    │                          │
│  │   system     │                          │
│  │   metrics    │                          │
│  └──────┬───────┘                          │
│         │                                   │
└─────────┼───────────────────────────────────┘
          │
          │ HTTP Push
          ▼
┌─────────────────────────────────────────────┐
│ Monitoring Server (monitoring.kw4jlb.com)  │
│                                             │
│  ┌──────────────┐      ┌──────────────┐   │
│  │ Prometheus   │      │ Loki         │   │
│  │ :9090        │      │ :3100        │   │
│  └──────────────┘      └──────────────┘   │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │ Grafana Dashboards & Alerts         │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

## What Was Configured

### 1. Asterisk Prometheus Module (`/etc/asterisk/prometheus.conf`)

Enables the built-in Prometheus exporter that exposes metrics about:
- Active channels and calls
- Channel states and durations
- Bridge states
- Endpoint states (SIP, IAX, etc.)
- System uptime and scrape duration

**Configuration:**
```ini
[general]
enabled = yes
core_metrics_enabled = yes
uri = metrics
```

### 2. Asterisk HTTP Server (`/etc/asterisk/http.conf`)

The HTTP server is required to serve Prometheus metrics.

**Key settings:**
- Enabled on port 8088
- Listens on all interfaces (0.0.0.0)
- Metrics available at: http://localhost:8088/metrics

### 3. Asterisk Logging (`/etc/asterisk/logger.conf`)

Configured to write comprehensive logs to `/var/log/asterisk/full`.

**Log levels captured:**
- notice, warning, error
- verbose (detailed messages)
- dtmf (DTMF tones)
- fax (fax events)

### 4. Grafana Alloy Installation

**Package:** `alloy` version 1.12.2-1 (arm64)
**Repository:** https://apt.grafana.com

Grafana Alloy is an OpenTelemetry Collector distribution that:
- Scrapes Prometheus metrics from Asterisk
- Tails and forwards log files to Loki
- Exports system metrics (node_exporter functionality)
- Monitors itself

### 5. Grafana Alloy Configuration (`/etc/alloy/config.alloy`)

The Alloy configuration includes:

**Prometheus Remote Write:**
- Target: http://monitoring.kw4jlb.com:9090/api/v1/write
- Scrapes Asterisk metrics every 15 seconds
- Scrapes system metrics every 15 seconds
- Scrapes Alloy self-metrics every 15 seconds

**Loki Remote Write:**
- Target: http://monitoring.kw4jlb.com:3100/loki/api/v1/push
- Tails /var/log/asterisk/full in real-time
- Forwards log entries with labels

**Labels applied to all data:**
- `monitor`: ionos-monitoring
- `environment`: production
- `instance`: node592420 (hostname)
- `service`: asterisk

## Files Modified/Created

### Asterisk Configuration Files
- `/etc/asterisk/prometheus.conf` - Prometheus exporter config
- `/etc/asterisk/http.conf` - HTTP server config (modified)
- `/etc/asterisk/logger.conf` - Logging configuration (modified)

### Grafana Alloy Files
- `/etc/alloy/config.alloy` - Main Alloy configuration
- `/etc/alloy/config.alloy.backup` - Backup of previous config
- `/etc/default/alloy` - Alloy environment variables
- `/usr/lib/systemd/system/alloy.service` - Systemd service unit
- `/var/lib/alloy/` - Alloy data directory

## Services Configured

### alloy.service
- **Status:** Enabled and running
- **User:** alloy (uid:997, gid:985)
- **Groups:** alloy, adm, systemd-journal
- **Command:** `/usr/bin/alloy run --storage.path=/var/lib/alloy/data /etc/alloy/config.alloy`
- **Restart:** Always (auto-restart on failure)

### asterisk.service
- **Status:** Active and running
- **Mounts:** /var/log/asterisk (dedicated mount point)

## Installation Script

The installation script (`install-asterisk-grafana-monitoring.sh`) automates the entire setup process:

### What the Script Does

1. **Configures Asterisk Prometheus Module**
   - Creates/updates `/etc/asterisk/prometheus.conf`
   - Enables metrics export

2. **Configures Asterisk HTTP Server**
   - Ensures HTTP server is enabled
   - Sets bind port to 8088
   - Configures session limits

3. **Configures Asterisk Logging**
   - Enables full logging to file
   - Creates log directory with proper permissions

4. **Restarts Asterisk**
   - Applies all configuration changes
   - Verifies metrics endpoint is accessible

5. **Installs Grafana Alloy**
   - Adds Grafana APT repository
   - Installs latest Alloy package
   - Handles existing installations

6. **Configures Grafana Alloy**
   - Creates configuration file
   - Sets up Prometheus scraping
   - Sets up Loki log forwarding
   - Configures system metrics export

7. **Starts Grafana Alloy**
   - Enables service on boot
   - Starts service
   - Verifies successful startup

8. **Verifies Installation**
   - Checks all services are running
   - Tests endpoints
   - Validates configuration

## Usage Instructions

### Prerequisites

- Ubuntu/Debian-based system with Asterisk installed
- Root/sudo access
- Network connectivity to monitoring server
- Asterisk already configured and running

### Installation Steps

1. **Copy the script to the target machine:**
   ```bash
   scp install-asterisk-grafana-monitoring.sh root@target-machine:/tmp/
   ```

2. **Customize configuration variables (optional):**

   Edit the script and modify these variables at the top:
   ```bash
   MONITORING_SERVER="monitoring.kw4jlb.com"
   PROMETHEUS_ENDPOINT="http://${MONITORING_SERVER}:9090/api/v1/write"
   LOKI_ENDPOINT="http://${MONITORING_SERVER}:3100/loki/api/v1/push"
   INSTANCE_NAME="$(hostname)"
   ENVIRONMENT="production"
   MONITOR_NAME="ionos-monitoring"
   ```

3. **Run the installation script:**
   ```bash
   sudo chmod +x /tmp/install-asterisk-grafana-monitoring.sh
   sudo /tmp/install-asterisk-grafana-monitoring.sh
   ```

4. **Follow the prompts:**
   - The script will ask for confirmation before proceeding
   - It will show progress for each step
   - Final verification will display the status of all components

### Post-Installation Verification

After installation, verify everything is working:

1. **Check Asterisk metrics endpoint:**
   ```bash
   curl http://localhost:8088/metrics
   ```

   Expected output: Prometheus-formatted metrics

2. **Check Asterisk logs:**
   ```bash
   tail -f /var/log/asterisk/full
   ```

   Should show ongoing log entries

3. **Check Alloy service:**
   ```bash
   systemctl status alloy
   journalctl -u alloy -f
   ```

   Should show "active (running)" and scraping logs

4. **Test remote connectivity:**
   ```bash
   curl -v http://monitoring.kw4jlb.com:9090/-/healthy
   curl -v http://monitoring.kw4jlb.com:3100/ready
   ```

5. **Verify metrics are being sent:**
   ```bash
   journalctl -u alloy -n 100 | grep "asterisk"
   ```

   Should show successful scrapes and pushes

## Customization

### Changing Monitoring Server

Edit `/etc/alloy/config.alloy` and update:

```alloy
prometheus.remote_write "monitoring_server" {
  endpoint {
    url = "http://YOUR_NEW_SERVER:9090/api/v1/write"
  }
}

loki.write "monitoring_server" {
  endpoint {
    url = "http://YOUR_NEW_SERVER:3100/loki/api/v1/push"
  }
}
```

Then reload Alloy:
```bash
systemctl reload alloy
```

### Changing Scrape Interval

Edit the `scrape_interval` in `/etc/alloy/config.alloy`:

```alloy
prometheus.scrape "asterisk_metrics" {
  scrape_interval = "30s"  # Change from 15s to 30s
  scrape_timeout  = "10s"
}
```

### Adding Additional Labels

Edit the `external_labels` section in `/etc/alloy/config.alloy`:

```alloy
external_labels = {
  monitor     = "ionos-monitoring",
  environment = "production",
  instance    = "node592420",
  service     = "asterisk",
  region      = "us-east",      # Add custom labels
  datacenter  = "dc1",
}
```

### Securing Asterisk Metrics Endpoint

To enable HTTP Basic Authentication on the metrics endpoint:

1. Edit `/etc/asterisk/prometheus.conf`:
   ```ini
   [general]
   enabled = yes
   core_metrics_enabled = yes
   uri = metrics
   auth_username = prometheus
   auth_password = YourSecurePassword123
   auth_realm = Asterisk Metrics
   ```

2. Update `/etc/alloy/config.alloy` to include authentication:
   ```alloy
   prometheus.scrape "asterisk_metrics" {
     targets         = discovery.relabel.asterisk_metrics.output
     forward_to      = [prometheus.remote_write.monitoring_server.receiver]
     job_name        = "integrations/asterisk"
     scrape_interval = "15s"
     scrape_timeout  = "10s"
     metrics_path    = "/metrics"

     basic_auth {
       username = "prometheus"
       password = "YourSecurePassword123"
     }
   }
   ```

3. Restart services:
   ```bash
   systemctl restart asterisk
   systemctl restart alloy
   ```

### Restricting HTTP Server Access

To make the HTTP server listen only on localhost:

1. Edit `/etc/asterisk/http.conf`:
   ```ini
   bindaddr=127.0.0.1  # Change from 0.0.0.0
   ```

2. Restart Asterisk:
   ```bash
   systemctl restart asterisk
   ```

Note: Only do this if Alloy runs on the same server.

## Troubleshooting

### Metrics Endpoint Not Accessible

**Symptoms:**
- `curl http://localhost:8088/metrics` fails
- 404 Not Found error

**Solutions:**
1. Check HTTP server is enabled:
   ```bash
   asterisk -rx "http show status"
   ```

2. Verify prometheus module is loaded:
   ```bash
   asterisk -rx "module show like prometheus"
   ```

3. Restart Asterisk:
   ```bash
   systemctl restart asterisk
   ```

### Alloy Not Sending Data

**Symptoms:**
- Alloy running but no data in Grafana
- Connection errors in logs

**Solutions:**
1. Check Alloy logs:
   ```bash
   journalctl -u alloy -n 100
   ```

2. Verify monitoring server is reachable:
   ```bash
   curl -v http://monitoring.kw4jlb.com:9090/-/healthy
   ```

3. Test configuration syntax:
   ```bash
   alloy fmt /etc/alloy/config.alloy
   ```

4. Check firewall rules:
   ```bash
   iptables -L -n | grep -E "(9090|3100)"
   ```

### Logs Not Being Collected

**Symptoms:**
- No Asterisk logs in Loki
- Permission errors in Alloy logs

**Solutions:**
1. Verify log file exists and is being written:
   ```bash
   ls -l /var/log/asterisk/full
   tail -f /var/log/asterisk/full
   ```

2. Check alloy user permissions:
   ```bash
   groups alloy
   # Should include: alloy, adm, systemd-journal
   ```

3. Add alloy to asterisk group:
   ```bash
   usermod -a -G asterisk alloy
   systemctl restart alloy
   ```

4. Check file permissions:
   ```bash
   chmod 644 /var/log/asterisk/full
   chown asterisk:asterisk /var/log/asterisk/full
   ```

### High CPU Usage

**Symptoms:**
- Alloy using excessive CPU
- System slowdown

**Solutions:**
1. Increase scrape interval in `/etc/alloy/config.alloy`:
   ```alloy
   scrape_interval = "30s"  # or "60s"
   ```

2. Reduce log verbosity in Asterisk
3. Disable system metrics if not needed

## Metrics Available

### Asterisk Metrics

The following metrics are exposed by Asterisk:

#### Core Metrics
- `asterisk_core_info` - Asterisk version and system info
- `asterisk_core_uptime_seconds` - Uptime in seconds
- `asterisk_core_last_reload_seconds` - Time since last reload
- `asterisk_core_scrape_time_ms` - Time to scrape metrics

#### Channel Metrics
- `asterisk_channels_count` - Current channel count
- `asterisk_channels_state` - Individual channel states (gauge)
- `asterisk_channels_duration_seconds` - Channel duration

#### Call Metrics
- `asterisk_calls_count` - Current call count
- `asterisk_calls_sum` - Total calls (counter)

#### Bridge Metrics
- `asterisk_bridges_count` - Current bridges
- `asterisk_bridges_channels_count` - Channels per bridge

#### Endpoint Metrics
- `asterisk_endpoints_count` - Endpoint count by state
- `asterisk_endpoints_channels_count` - Active channels per endpoint

#### PJSIP Metrics (if applicable)
- `asterisk_pjsip_contacts_count` - Contact states
- `asterisk_pjsip_subscriptions_count` - Subscription states

### System Metrics

The node_exporter component provides:
- CPU usage
- Memory usage
- Disk I/O
- Network traffic
- Filesystem usage
- Load averages

## Security Considerations

1. **HTTP Server Exposure:**
   - Currently binds to 0.0.0.0 (all interfaces)
   - Consider changing to 127.0.0.1 if not needed externally
   - Or use firewall rules to restrict access

2. **Metrics Authentication:**
   - No authentication enabled by default
   - Consider enabling Basic Auth for production

3. **Log Permissions:**
   - Alloy user needs read access to Asterisk logs
   - Achieved via group membership (asterisk group)

4. **Network Security:**
   - Data sent unencrypted to monitoring server
   - Consider using HTTPS/TLS for production
   - Use VPN or private network if possible

## Maintenance

### Updating Alloy

```bash
apt-get update
apt-get upgrade alloy
systemctl restart alloy
```

### Backup Configuration

```bash
# Backup Alloy config
cp /etc/alloy/config.alloy /backups/config.alloy.$(date +%Y%m%d)

# Backup Asterisk configs
tar -czf /backups/asterisk-monitoring-config-$(date +%Y%m%d).tar.gz \
  /etc/asterisk/prometheus.conf \
  /etc/asterisk/http.conf \
  /etc/asterisk/logger.conf
```

### Log Rotation

Asterisk logs are rotated by default. Verify with:
```bash
cat /etc/logrotate.d/asterisk
```

### Monitoring Alloy Health

```bash
# Check service status
systemctl status alloy

# View recent logs
journalctl -u alloy -n 50

# Check Alloy internal metrics
curl http://127.0.0.1:12345/metrics
```

## Additional Resources

- [Grafana Alloy Documentation](https://grafana.com/docs/alloy)
- [Asterisk Prometheus Module](https://wiki.asterisk.org/wiki/display/AST/Asterisk+18+Configuration_res_prometheus)
- [Asterisk HTTP Server](https://docs.asterisk.org/Configuration/Core-Configuration/Asterisk-Builtin-mini-HTTP-Server/)
- [Grafana Asterisk Integration](https://grafana.com/docs/grafana-cloud/monitor-infrastructure/integrations/integration-reference/integration-asterisk/)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Alloy logs: `journalctl -u alloy -n 100`
3. Review Asterisk logs: `tail -f /var/log/asterisk/full`
4. Verify connectivity to monitoring server
5. Check configuration syntax: `alloy fmt /etc/alloy/config.alloy`