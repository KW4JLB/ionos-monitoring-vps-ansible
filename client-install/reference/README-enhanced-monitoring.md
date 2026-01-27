# Enhanced Allstar Linux Monitoring

This directory contains enhanced monitoring components for Allstar Linux systems that extend the basic Asterisk monitoring with Allstar-specific metrics.

## Quick Start

### Basic Installation
Run the installation script as root:
```bash
sudo ./install-asterisk-grafana-monitoring.sh
```

This will install:
- Basic Asterisk Prometheus metrics
- System metrics (Node Exporter)
- Log shipping to Loki
- Enhanced Allstar-specific monitoring (if files are present)

### Enhanced Monitoring Components

When the Python monitoring files are present, the installer automatically configures enhanced monitoring:

#### RPT Metrics (`rpt_metrics.py`)
- Node statistics (links, connections, keyups, timeouts)
- Link quality metrics (noise levels, connection durations)
- System status (telemetry, linking, autopatch)

#### IAX2 Enhanced Metrics (`iax2_metrics.py`) 
- Channel quality (lag, jitter, connection states)
- Peer status (online/offline, ping times)
- Network statistics (packet counts, frame drops)

#### Allmon3 Integration (`allmon3_metrics.py`)
- Real-time node status via WebSocket
- Link topology and connection status
- User activity monitoring

#### Log Analytics (`log_metrics.py`)
- Connection event tracking
- Authentication failure monitoring
- Audio quality analysis from logs

#### Combined Server (`metrics_server.py`)
- Exposes all metrics on port 8089
- Health checking endpoint
- Prometheus-compatible format

## Configuration

### Variables
Edit the script variables at the top to customize:
```bash
MONITORING_SERVER="your-monitoring-server.com"
ENHANCED_MONITORING="yes"  # Set to "no" to disable
```

### Enhanced Monitoring Toggle
Set `ENHANCED_MONITORING="no"` in the script to install only basic monitoring.

## Monitoring Endpoints

- **Asterisk Metrics**: `http://localhost:8088/metrics`
- **Enhanced Metrics**: `http://localhost:8089/metrics` 
- **Health Check**: `http://localhost:8089/health`

## Services

- `asterisk.service` - Asterisk PBX
- `alloy.service` - Grafana Alloy (metric/log shipping)
- `allstar-metrics.service` - Enhanced monitoring server (if installed)

## Verification

Check all services are running:
```bash
systemctl status asterisk alloy allstar-metrics
```

Test metrics endpoints:
```bash
curl http://localhost:8088/metrics    # Basic Asterisk metrics
curl http://localhost:8089/metrics    # Enhanced Allstar metrics
curl http://localhost:8089/health     # Health check
```

## Files Structure

```
/opt/allstar-monitoring/          # Enhanced monitoring components
├── rpt_metrics.py               # RPT statistics collector
├── iax2_metrics.py              # IAX2 enhanced metrics
├── allmon3_metrics.py           # Allmon3 WebSocket integration
├── log_metrics.py               # Log-based analytics
└── metrics_server.py            # Combined HTTP server

/etc/alloy/
└── config.alloy                 # Grafana Alloy configuration

/etc/systemd/system/
└── allstar-metrics.service      # Enhanced monitoring service

/etc/asterisk/
├── prometheus.conf              # Asterisk Prometheus module
├── http.conf                    # HTTP server config
└── logger.conf                  # Logging configuration
```

## Troubleshooting

### Service Issues
```bash
# Check service logs
journalctl -u alloy -n 50
journalctl -u allstar-metrics -n 50
journalctl -u asterisk -n 50

# Restart services
systemctl restart alloy
systemctl restart allstar-metrics
```

### Configuration Issues
```bash
# Validate Alloy config
alloy fmt /etc/alloy/config.alloy

# Test metrics endpoints
curl -v http://localhost:8088/metrics
curl -v http://localhost:8089/metrics
```

### Enhanced Monitoring Issues
```bash
# Check if enhanced files exist
ls -la /opt/allstar-monitoring/

# Test Python scripts manually
cd /opt/allstar-monitoring
python3 rpt_metrics.py
python3 iax2_metrics.py
```

## Dashboards

The enhanced metrics enable creation of detailed dashboards for:
- Node health and status overview
- Network performance and link quality
- Activity monitoring and usage patterns
- Security monitoring and alerts

## Restoration

To restore original configuration:
```bash
# Find backup files
ls /etc/alloy/config.alloy.backup.*
ls /etc/asterisk/*.backup.*

# Restore and restart
cp /etc/alloy/config.alloy.backup.YYYYMMDD_HHMMSS /etc/alloy/config.alloy
systemctl restart alloy
```

## Support

This enhanced monitoring extends the standard Asterisk integration with Allstar-specific metrics for better operational visibility into Allstar Linux nodes.