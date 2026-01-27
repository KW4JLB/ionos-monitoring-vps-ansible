# Raspberry Pi 3B+ Monitoring Constraints & Lessons Learned

**Date Created**: January 27, 2026  
**System**: node592420 (Raspberry Pi 3B+)  
**Purpose**: Document hardware limitations, challenges, and working solutions for future reference

## Hardware Constraints

### Physical Specifications
- **Hardware**: Raspberry Pi 3B+
- **RAM**: 905Mi total, ~147Mi available under normal load
- **Storage**: SD Card (high I/O latency, write cycle limitations)
- **CPU**: Quad-core ARM Cortex-A53 @ 1.4GHz
- **Network**: 100Mbps Ethernet + WiFi

### Performance Boundaries Identified
- **System Load**: Must stay below 3.0 for stability
- **Memory Pressure**: Swap usage above 700Mi indicates stress
- **Disk I/O**: High zram I/O indicates memory pressure and disk thrashing
- **Critical Threshold**: System reboots occurred when load exceeded 3.5 consistently

## Challenges Encountered

### 1. Enhanced Metrics Collection Overload
**Problem**: Full enhanced metrics (RPT, IAX2, Allmon3, log analysis) caused:
- System load spikes above 3.6
- Memory exhaustion and heavy swap usage
- High zram read/write operations
- System reboots under load

**Root Causes**:
- Multiple Python processes making frequent asterisk CLI calls
- Alloy WAL operations writing to disk every 15-30 seconds
- Complex log parsing consuming CPU cycles
- VSCode server adding additional resource pressure

### 2. Configuration Complexity
**Problem**: Alloy configuration syntax errors causing service failures
- Missing commas in arrays and field lists
- Complex collector configurations failing validation
- Service restart loops when config invalid

### 3. Authentication Confusion
**Problem**: Mixing Grafana user credentials with Prometheus/Loki endpoint auth
- Grafana UI requires user credentials (see `/home/kj4kpy/ionos-monitoring-vps-ansible/credentials.txt`)
- Prometheus/Loki endpoints don't require authentication
- Initially tried wrong credentials for wrong services

### 4. Dashboard Mismatch
**Problem**: Enhanced System Health dashboard expected node_exporter metrics we weren't collecting
- Dashboard queries for `node_load1`, `node_cpu_seconds_total`, etc.
- Minimal config only sent RPT metrics
- Missing system health visibility

## Solutions Attempted & Results

### ❌ Failed Approaches

#### Full Enhanced Metrics (Original Implementation)
```yaml
Services: RPT + IAX2 + Allmon3 + Log Analysis + System metrics
Intervals: 15-30 seconds
Result: FAILED - System overload, reboots, unsustainable
```

#### Completely Minimal (RPT Only)
```yaml
Services: RPT active links only
Intervals: 2 minutes
Result: PARTIALLY FAILED - System stable but dashboard broken
```

### ✅ Working Solutions

#### Balanced Essential Monitoring (Final Implementation)
```yaml
Services: RPT + Essential system metrics (CPU, memory, disk, network, temperature)
Intervals: 2 minutes
Collectors: Disabled heavy collectors (processes, interrupts, complex filesystem)
WAL: Optimized settings (1h truncation, minimal keepalive)
Result: SUCCESS - System stable (load ~2.2), dashboard functional
```

**Key Configuration**:
```alloy
// System metrics with disabled heavy collectors
prometheus.exporter.unix "system" {
  include_exporter_metrics = false
  disable_collectors = [
    "mdadm", "wifi", "powersupplyclass", "dmi", "thermal_zone", 
    "cooling_device", "processes", "interrupts"
  ]
}

// 2-minute scrape intervals
scrape_interval = "2m"

// Optimized WAL settings
wal {
  truncate_frequency = "1h"
  min_keepalive_time = "30s"
  max_keepalive_time = "5m"
}
```

## Operational Boundaries Established

### Resource Limits
- **Maximum System Load**: 2.5 sustained (alert at 3.0)
- **Memory Usage**: Keep available memory above 100Mi
- **Swap Usage**: Should not exceed 800Mi consistently
- **Scrape Intervals**: Minimum 2 minutes for stability

### Service Priorities (in order)
1. **Asterisk Operation** (core radio functionality)
2. **System Stability** (prevent reboots/crashes)
3. **Essential Monitoring** (basic health + RPT status)
4. **Enhanced Monitoring** (detailed metrics if resources allow)
5. **Development Tools** (VSCode server - disable under load)

### Monitoring Capabilities
**✅ Sustainable Metrics**:
- RPT active links and basic status
- System health (CPU, memory, load, disk usage)
- Network throughput and errors
- Basic temperature monitoring
- Filesystem usage and disk I/O

**❌ Unsustainable Metrics** (Pi 3B+ constraints):
- Detailed IAX2 peer analysis
- Real-time log parsing and analysis
- High-frequency noise level monitoring
- Complex Allstar protocol deep-inspection
- Sub-minute metric collection intervals

## Configuration Files & Locations

### Current Working Configurations
- **Alloy Config**: `/home/kj4kpy/ionos-monitoring-vps-ansible/client-install/ultra-minimal-config.alloy`
- **Minimal Metrics**: `/home/kj4kpy/ionos-monitoring-vps-ansible/client-install/minimal_metrics_server.py`
- **Dashboard**: `/home/kj4kpy/ionos-monitoring-vps-ansible/roles/grafana-asterisk/files/dashboards/allstar-minimal.json`

### Service Configuration
```systemd
# /etc/systemd/system/allstar-metrics.service
Nice=10
IOSchedulingClass=3
RestartSec=30
```

## Lessons for Future Sessions

### Before Making Changes
1. **Check current system load** with `uptime`
2. **Monitor memory pressure** with `free -h`
3. **Verify swap usage** - heavy swap = trouble ahead
4. **Test configuration syntax** before applying

### Safe Change Process
1. Start with minimal impact changes
2. Monitor system load for 5-10 minutes after changes
3. Gradually add complexity only if system remains stable
4. Always have rollback plan (working config files)
5. Document what works and what doesn't

### Red Flags - Stop Immediately
- System load above 3.5
- Available memory below 50Mi
- Swap usage approaching 900Mi
- High zram I/O operations
- Service restart loops

### Performance Monitoring Commands
```bash
# System health check
uptime && free -h

# Service status
systemctl is-active alloy.service allstar-metrics.service

# Check for resource issues
ps aux --sort=-%cpu | head -10
```

## Success Metrics

The current balanced approach successfully provides:
- **System Stability**: Load average ~2.2 (down from 3.6+)
- **Essential Monitoring**: All key dashboard panels populated
- **Operational Resilience**: No system reboots or service failures
- **Resource Efficiency**: Minimal disk I/O, controlled memory usage
- **Functional Visibility**: Core Allstar and system health monitoring

**Bottom Line**: Raspberry Pi 3B+ can handle essential monitoring but cannot support comprehensive enhanced metrics without compromising operational stability.