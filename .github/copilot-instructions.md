# GitHub Copilot Instructions - Allstar Monitoring Project

## Project Overview

This project provides monitoring infrastructure for Allstar (app_rpt) repeater systems running on **Raspberry Pi 3B+ hardware**. The system has **strict performance constraints** that must be respected to maintain operational stability.

## Critical Hardware Constraints

### Target Hardware: Raspberry Pi 3B+
- **RAM**: 905Mi total, ~147Mi available under normal load
- **Storage**: SD Card (high I/O latency, write cycle limitations)  
- **CPU**: Quad-core ARM Cortex-A53 @ 1.4GHz
- **Network**: 100Mbps Ethernet

### Performance Boundaries - NEVER EXCEED
- **System Load**: Must stay below 3.0 (alert at 2.5, critical at 3.5+)
- **Available Memory**: Keep above 100Mi (critical below 50Mi)
- **Swap Usage**: Should not exceed 800Mi consistently
- **Disk I/O**: High zram usage indicates memory pressure and impending failure

## Service Priority Hierarchy (STRICT ORDER)

1. **Asterisk Operation** (core radio functionality) - NEVER compromise
2. **System Stability** (prevent reboots/crashes) - NEVER compromise  
3. **Essential Monitoring** (basic health + RPT status) - Current sustainable level
4. **Enhanced Monitoring** (detailed metrics) - ONLY if resources allow
5. **Development Tools** (VSCode, etc.) - Disable under load

## Working Solutions (PROVEN STABLE)

### ✅ Sustainable Monitoring Approach
```yaml
Configuration: ultra-minimal-config.alloy
Service: minimal_metrics_server.py  
Intervals: 2 minutes minimum
Collectors: Essential system metrics only (CPU, memory, load, network, disk, temperature)
WAL Settings: 1h truncation, minimal keepalive
Result: System load ~2.2, stable operation
```

### ✅ Safe Configuration Patterns
```alloy
// Always use 2-minute minimum intervals
scrape_interval = "2m"

// Disable heavy collectors
disable_collectors = [
  "processes", "interrupts", "mdadm", "wifi", "powersupplyclass", 
  "dmi", "thermal_zone", "cooling_device"
]

// Optimized WAL settings
wal {
  truncate_frequency = "1h"
  min_keepalive_time = "30s" 
  max_keepalive_time = "5m"
}
```

## Failed Approaches (DO NOT REPEAT)

### ❌ Enhanced Metrics Collection
- **Problem**: RPT + IAX2 + Allmon3 + Log Analysis caused system overload
- **Symptoms**: Load >3.6, memory exhaustion, system reboots
- **Root Cause**: Multiple Python processes + frequent asterisk CLI calls + WAL disk I/O
- **Verdict**: UNSUSTAINABLE on Pi 3B+

### ❌ Sub-Minute Collection Intervals  
- **Problem**: 15-30 second intervals overwhelm the system
- **Impact**: High disk I/O, memory pressure, service failures
- **Verdict**: 2-minute minimum intervals required

### ❌ Complex Log Parsing
- **Problem**: Real-time log analysis consumes excessive CPU
- **Impact**: System instability, resource exhaustion
- **Verdict**: Basic log metrics only, no complex parsing

## Configuration Guidelines for Copilot

### When Suggesting Changes
1. **ALWAYS check system impact first**: `uptime && free -h`
2. **Start with minimal changes**: Test one component at a time
3. **Monitor for 10 minutes**: Watch load/memory after changes
4. **Have rollback plan**: Keep working configurations available

### Red Flags - Stop Immediately If You See
- System load above 3.5
- Available memory below 50Mi
- Swap usage approaching 900Mi
- Service restart loops
- High zram I/O operations

### Safe Change Process
```bash
# 1. Check current system health
uptime && free -h

# 2. Backup working config
cp /etc/alloy/config.alloy /etc/alloy/config.alloy.backup

# 3. Test syntax before applying
alloy fmt --write config.alloy  # Validate syntax

# 4. Apply changes gradually
systemctl restart alloy.service

# 5. Monitor impact
watch -n 30 'uptime && free -h'
```

## Specific Technical Constraints

### Monitoring Capabilities
**✅ SUSTAINABLE**:
- RPT active links and basic status
- System health (CPU, memory, load, disk usage)  
- Network throughput and basic errors
- Temperature monitoring (basic hwmon)
- Filesystem usage and basic disk I/O

**❌ UNSUSTAINABLE**:
- Detailed IAX2 peer analysis
- Real-time log parsing and analysis
- High-frequency noise level monitoring
- Complex Allstar protocol inspection
- Sub-minute metric collection
- Multiple concurrent Python collectors

### Authentication Patterns
- **Grafana UI**: Requires user credentials (see `credentials.txt`)
- **Prometheus/Loki**: NO authentication required
- **Alloy**: Uses HTTP endpoints without auth

### File Organization
- **Working configs**: `/client-install/` (root level)
- **Reference/backup**: `/client-install/reference/`
- **Archive**: `/client-install/archive/`
- **Documentation**: `/client-install/README-*.md`

## Alloy Configuration Syntax Notes

### Common Syntax Errors to Avoid
```alloy
// ❌ Missing commas in arrays
disable_collectors = [
  "item1", "item2", "item3"  // Missing comma after item3
]

// ✅ Correct syntax  
disable_collectors = [
  "item1", "item2", "item3",
]

// ❌ Missing commas in objects
external_labels = {
  key1 = "value1"
  key2 = "value2"  // Missing comma
}

// ✅ Correct syntax
external_labels = {
  key1 = "value1",
  key2 = "value2",
}
```

## Emergency Procedures

### If System Load > 3.5
1. **Stop enhanced monitoring**: `systemctl stop allstar-metrics.service`
2. **Reduce Alloy frequency**: Switch to ultra-minimal config
3. **Monitor recovery**: Wait for load to drop below 2.5
4. **Investigate cause**: Check memory, swap, I/O patterns

### If Services Failing
1. **Check syntax errors**: `journalctl -u alloy.service -n 20`
2. **Restore working config**: `cp config.alloy.backup config.alloy`
3. **Restart services**: `systemctl restart alloy.service`
4. **Verify stability**: Monitor for 10+ minutes

## Success Metrics

A successful configuration should maintain:
- System load average < 2.5 sustained
- Available memory > 100Mi
- Swap usage < 800Mi  
- No service restart loops
- Essential dashboards populated
- Asterisk operation unaffected

## Online Documentation References
Grafana: https://grafana.com/docs/grafana/latest/
Prometheus: https://prometheus.io/docs/introduction/overview/
Loki: https://grafana.com/docs/loki/latest/
Alloy: https://grafana.com/docs/alloy/latest/
Allstar Linux: https://allstarlink.github.io/adv-topics/

## Key Takeaway for Copilot

**Operations come first, monitoring second.** Always prioritize system stability over comprehensive monitoring. The Pi 3B+ can handle essential monitoring but cannot support enhanced metrics without compromising the primary Asterisk/Allstar functionality.