#!/bin/bash
################################################################################
# Asterisk Grafana Cloud Monitoring Integration - Installation Script
################################################################################
# This script installs and configures the Grafana Alloy agent to send
# Asterisk metrics and logs to a Prometheus/Loki monitoring server.
#
# Based on: https://grafana.com/docs/grafana-cloud/monitor-infrastructure/integrations/integration-reference/integration-asterisk/
#
# What this script does:
# 1. Configures Asterisk to enable Prometheus metrics endpoint
# 2. Configures Asterisk HTTP server
# 3. Configures Asterisk logging to file
# 4. Installs Grafana Alloy agent
# 5. Configures Alloy to scrape Asterisk metrics and logs
# 6. Enables and starts services
#
# Usage: sudo ./install-asterisk-grafana-monitoring.sh
################################################################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration variables - CUSTOMIZE THESE FOR YOUR SETUP
MONITORING_SERVER="monitoring.kw4jlb.com"
PROMETHEUS_ENDPOINT="http://${MONITORING_SERVER}:9090/api/v1/write"
LOKI_ENDPOINT="http://${MONITORING_SERVER}:3100/loki/api/v1/push"
INSTANCE_NAME="$(hostname)"
ENVIRONMENT="production"
MONITOR_NAME="ionos-monitoring"

# Asterisk configuration
ASTERISK_HTTP_PORT="8088"
ASTERISK_METRICS_PATH="/metrics"

# Enhanced monitoring configuration
ENHANCED_MONITORING="yes"  # Set to "no" to disable enhanced monitoring
ENHANCED_METRICS_PORT="8089"
CLIENT_INSTALL_DIR="$(dirname "$(readlink -f "$0")")"  # Directory where this script is located

################################################################################
# Helper Functions
################################################################################

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

################################################################################
# Enhanced Monitoring Functions
################################################################################

install_enhanced_monitoring() {
    if [ "$ENHANCED_MONITORING" != "yes" ]; then
        log_info "Skipping enhanced monitoring installation"
        return 0
    fi

    log_info "Installing enhanced Allstar monitoring components..."

    # Create directory for enhanced monitoring
    local ENHANCED_DIR="/opt/allstar-monitoring"
    mkdir -p "$ENHANCED_DIR"

    # Copy Python collectors
    cp "$CLIENT_INSTALL_DIR/rpt_metrics.py" "$ENHANCED_DIR/" 2>/dev/null || log_warn "rpt_metrics.py not found, skipping"
    cp "$CLIENT_INSTALL_DIR/iax2_metrics.py" "$ENHANCED_DIR/" 2>/dev/null || log_warn "iax2_metrics.py not found, skipping" 
    cp "$CLIENT_INSTALL_DIR/allmon3_metrics.py" "$ENHANCED_DIR/" 2>/dev/null || log_warn "allmon3_metrics.py not found, skipping"
    cp "$CLIENT_INSTALL_DIR/log_metrics.py" "$ENHANCED_DIR/" 2>/dev/null || log_warn "log_metrics.py not found, skipping"
    cp "$CLIENT_INSTALL_DIR/metrics_server.py" "$ENHANCED_DIR/" 2>/dev/null || log_warn "metrics_server.py not found, skipping"

    # Make scripts executable
    chmod +x "$ENHANCED_DIR"/*.py 2>/dev/null

    # Install systemd service if it exists
    if [ -f "$CLIENT_INSTALL_DIR/allstar-metrics.service" ]; then
        # Update service file paths
        sed "s|/home/kj4kpy/allstar-monitoring|$ENHANCED_DIR|g" \
            "$CLIENT_INSTALL_DIR/allstar-metrics.service" > /etc/systemd/system/allstar-metrics.service
        
        systemctl daemon-reload
        systemctl enable allstar-metrics.service
        systemctl start allstar-metrics.service
        
        if systemctl is-active --quiet allstar-metrics; then
            log_info "✓ Enhanced monitoring service started"
        else
            log_warn "Enhanced monitoring service failed to start"
        fi
    else
        log_warn "allstar-metrics.service not found, skipping service installation"
    fi

    log_info "✓ Enhanced monitoring components installed"
}

################################################################################
# Step 1: Configure Asterisk Prometheus Module
################################################################################

configure_asterisk_prometheus() {
    log_info "Configuring Asterisk Prometheus module..."

    local PROMETHEUS_CONF="/etc/asterisk/prometheus.conf"

    # Backup existing config if present
    if [ -f "$PROMETHEUS_CONF" ]; then
        log_warn "Backing up existing prometheus.conf"
        cp "$PROMETHEUS_CONF" "${PROMETHEUS_CONF}.backup.$(date +%Y%m%d_%H%M%S)"
    fi

    # Create prometheus.conf
    cat > "$PROMETHEUS_CONF" <<'EOF'
;
; res_prometheus Module configuration for Asterisk
;

[general]
enabled = yes                     ; Enable/disable all statistic generation.
core_metrics_enabled = yes        ; Enable/disable core metrics.
uri = metrics                     ; The HTTP route to expose metrics on.

; auth_username = Asterisk        ; Optional: Enable Basic Auth
; auth_password =                 ; Optional: Password for Basic Auth
; auth_realm =                    ; Optional: Realm for authentication
EOF

    log_info "✓ Prometheus module configured at $PROMETHEUS_CONF"
}

################################################################################
# Step 2: Configure Asterisk HTTP Server
################################################################################

configure_asterisk_http() {
    log_info "Configuring Asterisk HTTP server..."

    local HTTP_CONF="/etc/asterisk/http.conf"

    # Backup existing config if present
    if [ -f "$HTTP_CONF" ]; then
        log_warn "Backing up existing http.conf"
        cp "$HTTP_CONF" "${HTTP_CONF}.backup.$(date +%Y%m%d_%H%M%S)"
    fi

    # Check if http.conf already has required settings
    if grep -q "enabled=yes" "$HTTP_CONF" 2>/dev/null && grep -q "bindport=$ASTERISK_HTTP_PORT" "$HTTP_CONF" 2>/dev/null; then
        log_warn "HTTP server appears already configured in $HTTP_CONF"
        log_warn "Verify manually that bindport=$ASTERISK_HTTP_PORT and enabled=yes"
    else
        log_info "Adding HTTP server configuration to $HTTP_CONF"

        # Append to existing config or create new
        cat >> "$HTTP_CONF" <<EOF

; ============================================================================
; Grafana Monitoring Integration - Added $(date)
; ============================================================================
[general]
enabled=yes                        ; Enable Asterisk HTTP server
enablestatic=yes                   ; Enable serving static content
bindaddr=0.0.0.0                   ; Listen on all interfaces
                                   ; SECURITY NOTE: Change to 127.0.0.1 for localhost only
bindport=$ASTERISK_HTTP_PORT       ; HTTP port for Asterisk web services
prefix=                            ; URL prefix (empty = root)
sessionlimit=100                   ; Maximum concurrent HTTP sessions
session_inactivity=30000           ; Session timeout (ms) - 30 seconds
session_keep_alive=15000           ; Keep-alive interval (ms) - 15 seconds
EOF
    fi

    log_info "✓ HTTP server configured at $HTTP_CONF"
}

################################################################################
# Step 3: Configure Asterisk Logging
################################################################################

configure_asterisk_logging() {
    log_info "Configuring Asterisk logging..."

    local LOGGER_CONF="/etc/asterisk/logger.conf"

    # Backup existing config
    if [ -f "$LOGGER_CONF" ]; then
        cp "$LOGGER_CONF" "${LOGGER_CONF}.backup.$(date +%Y%m%d_%H%M%S)"
    fi

    # Check if full log is already configured
    if grep -q "^full =>" "$LOGGER_CONF" 2>/dev/null; then
        log_info "✓ Full logging already configured in $LOGGER_CONF"
    else
        log_warn "Adding full log configuration to $LOGGER_CONF"

        # Add to [logfiles] section or create it
        if grep -q "^\[logfiles\]" "$LOGGER_CONF" 2>/dev/null; then
            # Append to existing [logfiles] section
            sed -i '/^\[logfiles\]/a full => notice,warning,error,verbose,dtmf,fax' "$LOGGER_CONF"
        else
            # Create [logfiles] section
            cat >> "$LOGGER_CONF" <<EOF

[logfiles]
full => notice,warning,error,verbose,dtmf,fax
EOF
        fi
    fi

    # Ensure log directory exists with proper permissions
    mkdir -p /var/log/asterisk
    chown asterisk:asterisk /var/log/asterisk

    log_info "✓ Logging configured to /var/log/asterisk/full"
}

################################################################################
# Step 4: Restart Asterisk to Apply Changes
################################################################################

restart_asterisk() {
    log_info "Restarting Asterisk to apply configuration changes..."

    systemctl restart asterisk

    # Wait a moment for Asterisk to fully start
    sleep 3

    # Verify Asterisk is running
    if systemctl is-active --quiet asterisk; then
        log_info "✓ Asterisk is running"
    else
        log_error "Asterisk failed to start. Check logs: journalctl -u asterisk -n 50"
        exit 1
    fi

    # Test metrics endpoint
    log_info "Testing Prometheus metrics endpoint..."
    if curl -s -f "http://localhost:$ASTERISK_HTTP_PORT$ASTERISK_METRICS_PATH" > /dev/null; then
        log_info "✓ Metrics endpoint is accessible at http://localhost:$ASTERISK_HTTP_PORT$ASTERISK_METRICS_PATH"
    else
        log_error "Metrics endpoint not accessible. Check Asterisk configuration."
        log_error "Try: curl http://localhost:$ASTERISK_HTTP_PORT$ASTERISK_METRICS_PATH"
        exit 1
    fi
}

################################################################################
# Step 5: Install Grafana Alloy
################################################################################

install_grafana_alloy() {
    log_info "Installing Grafana Alloy..."

    # Check if already installed
    if command -v alloy &> /dev/null; then
        local INSTALLED_VERSION=$(dpkg -l | grep "^ii.*alloy" | awk '{print $3}')
        log_warn "Grafana Alloy is already installed (version: $INSTALLED_VERSION)"
        read -p "Do you want to reinstall/upgrade? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Skipping Alloy installation"
            return 0
        fi
    fi

    # Install dependencies
    log_info "Installing dependencies..."
    apt-get update
    apt-get install -y gpg curl

    # Add Grafana GPG key
    log_info "Adding Grafana GPG key..."
    mkdir -p /etc/apt/keyrings/
    wget -q -O - https://apt.grafana.com/gpg.key | gpg --dearmor > /etc/apt/keyrings/grafana.gpg

    # Add Grafana repository
    log_info "Adding Grafana repository..."
    echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" | \
        tee /etc/apt/sources.list.d/grafana.list

    # Update and install
    log_info "Installing Grafana Alloy package..."
    apt-get update
    apt-get install -y alloy

    log_info "✓ Grafana Alloy installed"
}

################################################################################
# Step 6: Configure Grafana Alloy
################################################################################

configure_grafana_alloy() {
    log_info "Configuring Grafana Alloy..."

    local ALLOY_CONFIG="/etc/alloy/config.alloy"

    # Backup existing config if present
    if [ -f "$ALLOY_CONFIG" ]; then
        log_warn "Backing up existing Alloy configuration"
        cp "$ALLOY_CONFIG" "${ALLOY_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"
    fi

    # Use enhanced config if available and enabled
    if [ "$ENHANCED_MONITORING" = "yes" ] && [ -f "$CLIENT_INSTALL_DIR/enhanced-config.alloy" ]; then
        log_info "Using enhanced Alloy configuration"
        # Replace variables in enhanced config
        sed -e "s/monitoring\.kw4jlb\.com/$MONITORING_SERVER/g" \
            -e "s/node592420/$INSTANCE_NAME/g" \
            -e "s/ionos-monitoring/$MONITOR_NAME/g" \
            -e "s/production/$ENVIRONMENT/g" \
            "$CLIENT_INSTALL_DIR/enhanced-config.alloy" > "$ALLOY_CONFIG"
    else
        log_info "Using basic Alloy configuration"
        # Create basic Alloy configuration
        cat > "$ALLOY_CONFIG" <<EOF
// Grafana Alloy Configuration for Asterisk Monitoring
// Scrapes metrics locally and pushes to monitoring server
// For reference: https://grafana.com/docs/alloy
// Generated: $(date)

logging {
  level  = "info"
  format = "logfmt"
}

// ============================================================================
// Prometheus Remote Write Endpoint
// ============================================================================
prometheus.remote_write "monitoring_server" {
  endpoint {
    url = "$PROMETHEUS_ENDPOINT"

    queue_config {
      max_shards = 1
    }
  }

  external_labels = {
    monitor     = "$MONITOR_NAME",
    environment = "$ENVIRONMENT",
    instance    = "$INSTANCE_NAME",
    service     = "asterisk",
  }
}

// ============================================================================
// Loki Remote Write Endpoint
// ============================================================================
loki.write "monitoring_server" {
  endpoint {
    url = "$LOKI_ENDPOINT"
  }

  external_labels = {
    monitor     = "$MONITOR_NAME",
    environment = "$ENVIRONMENT",
    instance    = "$INSTANCE_NAME",
    service     = "asterisk",
  }
}

// ============================================================================
// Asterisk Prometheus Metrics Scraping
// ============================================================================
discovery.relabel "asterisk_metrics" {
  targets = [{
    __address__ = "localhost:$ASTERISK_HTTP_PORT",
  }]

  rule {
    target_label = "instance"
    replacement  = "$INSTANCE_NAME"
  }

  rule {
    target_label = "job"
    replacement  = "asterisk"
  }
}

prometheus.scrape "asterisk_metrics" {
  targets         = discovery.relabel.asterisk_metrics.output
  forward_to      = [prometheus.remote_write.monitoring_server.receiver]
  job_name        = "integrations/asterisk"
  scrape_interval = "15s"
  scrape_timeout  = "10s"
  metrics_path    = "$ASTERISK_METRICS_PATH"
}

// ============================================================================
// Asterisk Logs Collection
// ============================================================================
local.file_match "asterisk_logs" {
  path_targets = [{
    __address__ = "localhost",
    __path__    = "/var/log/asterisk/full",
    instance    = "$INSTANCE_NAME",
    job         = "asterisk-logs",
  }]
}

loki.source.file "asterisk_logs" {
  targets    = local.file_match.asterisk_logs.targets
  forward_to = [loki.write.monitoring_server.receiver]
}

// ============================================================================
// System Metrics (Node Exporter)
// ============================================================================
prometheus.exporter.unix "system" {
  include_exporter_metrics = true
  disable_collectors       = ["mdadm"]
}

prometheus.scrape "system_metrics" {
  targets         = prometheus.exporter.unix.system.targets
  forward_to      = [prometheus.remote_write.monitoring_server.receiver]
  job_name        = "node-exporter"
  scrape_interval = "15s"
}

// ============================================================================
// Alloy Self-Monitoring
// ============================================================================
prometheus.scrape "alloy_self" {
  targets = [{
    job         = "alloy",
    __address__ = "127.0.0.1:12345",
  }]

  forward_to      = [prometheus.remote_write.monitoring_server.receiver]
  scrape_interval = "15s"
}
EOF
    fi

    # Set proper permissions
    chown alloy:alloy "$ALLOY_CONFIG"
    chmod 644 "$ALLOY_CONFIG"

    # Ensure alloy user can read Asterisk logs
    usermod -a -G asterisk alloy 2>/dev/null || true

    log_info "✓ Alloy configured at $ALLOY_CONFIG"
}

################################################################################
# Step 7: Enable and Start Grafana Alloy
################################################################################

start_grafana_alloy() {
    log_info "Starting Grafana Alloy service..."

    # Reload systemd
    systemctl daemon-reload

    # Enable service to start on boot
    systemctl enable alloy

    # Start service
    systemctl restart alloy

    # Wait a moment for service to start
    sleep 3

    # Check status
    if systemctl is-active --quiet alloy; then
        log_info "✓ Grafana Alloy is running"
    else
        log_error "Grafana Alloy failed to start. Check logs: journalctl -u alloy -n 50"
        exit 1
    fi
}

################################################################################
# Step 8: Verify Installation
################################################################################

verify_installation() {
    log_info "Verifying installation..."

    echo ""
    echo "=========================================="
    echo "Installation Verification"
    echo "=========================================="

    # Check Asterisk
    if systemctl is-active --quiet asterisk; then
        echo -e "${GREEN}✓${NC} Asterisk service: RUNNING"
    else
        echo -e "${RED}✗${NC} Asterisk service: NOT RUNNING"
    fi

    # Check metrics endpoint
    if curl -s -f "http://localhost:$ASTERISK_HTTP_PORT$ASTERISK_METRICS_PATH" > /dev/null; then
        echo -e "${GREEN}✓${NC} Metrics endpoint: ACCESSIBLE"
    else
        echo -e "${RED}✗${NC} Metrics endpoint: NOT ACCESSIBLE"
    fi

    # Check log file
    if [ -f "/var/log/asterisk/full" ]; then
        echo -e "${GREEN}✓${NC} Asterisk logs: FOUND (/var/log/asterisk/full)"
    else
        echo -e "${RED}✗${NC} Asterisk logs: NOT FOUND"
    fi

    # Check Alloy
    if systemctl is-active --quiet alloy; then
        echo -e "${GREEN}✓${NC} Grafana Alloy service: RUNNING"
    else
        echo -e "${RED}✗${NC} Grafana Alloy service: NOT RUNNING"
    fi

    # Check Alloy configuration
    if alloy fmt /etc/alloy/config.alloy > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Alloy configuration: VALID"
    else
        echo -e "${YELLOW}⚠${NC} Alloy configuration: CHECK SYNTAX"
    fi

    # Check enhanced monitoring if enabled
    if [ "$ENHANCED_MONITORING" = "yes" ]; then
        if systemctl is-active --quiet allstar-metrics 2>/dev/null; then
            echo -e "${GREEN}✓${NC} Enhanced monitoring service: RUNNING"
        else
            echo -e "${RED}✗${NC} Enhanced monitoring service: NOT RUNNING"
        fi
        
        if curl -s -f "http://localhost:$ENHANCED_METRICS_PORT/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} Enhanced metrics endpoint: ACCESSIBLE"
        else
            echo -e "${RED}✗${NC} Enhanced metrics endpoint: NOT ACCESSIBLE"
        fi
    fi

    echo ""
    echo "=========================================="
    echo "Configuration Summary"
    echo "=========================================="
    echo "Monitoring Server: $MONITORING_SERVER"
    echo "Prometheus Endpoint: $PROMETHEUS_ENDPOINT"
    echo "Loki Endpoint: $LOKI_ENDPOINT"
    echo "Instance Name: $INSTANCE_NAME"
    echo "Environment: $ENVIRONMENT"
    echo ""
    echo "Asterisk Metrics: http://localhost:$ASTERISK_HTTP_PORT$ASTERISK_METRICS_PATH"
    echo "Asterisk Logs: /var/log/asterisk/full"
    echo ""
}

################################################################################
# Step 9: Post-Installation Instructions
################################################################################

show_post_install_info() {
    echo "=========================================="
    echo "Post-Installation Notes"
    echo "=========================================="
    echo ""
    echo "1. Verify metrics are being scraped:"
    echo "   curl http://localhost:$ASTERISK_HTTP_PORT$ASTERISK_METRICS_PATH"
    echo ""
    echo "2. Check Alloy is collecting data:"
    echo "   journalctl -u alloy -f"
    echo ""
    echo "3. Verify Asterisk logs are being written:"
    echo "   tail -f /var/log/asterisk/full"
    echo ""
    echo "4. Test remote connectivity to monitoring server:"
    echo "   curl -v $MONITORING_SERVER:9090/-/healthy"
    echo ""
    echo "5. Configuration files:"
    echo "   - Asterisk Prometheus: /etc/asterisk/prometheus.conf"
    echo "   - Asterisk HTTP: /etc/asterisk/http.conf"
    echo "   - Asterisk Logger: /etc/asterisk/logger.conf"
    echo "   - Grafana Alloy: /etc/alloy/config.alloy"
    echo ""
    echo "6. Service management:"
    echo "   systemctl status asterisk"
    echo "   systemctl status alloy"
    echo "   systemctl restart asterisk"
    echo "   systemctl restart alloy"
    echo ""
    echo "7. To customize the configuration, edit:"
    echo "   /etc/alloy/config.alloy"
    echo "   Then reload: systemctl reload alloy"
    echo ""
    echo "=========================================="
    echo -e "${GREEN}Installation Complete!${NC}"
    echo "=========================================="
}

################################################################################
# Main Installation Flow
################################################################################

main() {
    echo "=========================================="
    echo "Asterisk Grafana Monitoring Integration"
    echo "Installation Script"
    echo "=========================================="
    echo ""

    check_root

    # Confirm before proceeding
    read -p "This will configure Asterisk and install Grafana Alloy. Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_warn "Installation cancelled"
        exit 0
    fi

    echo ""
    log_info "Starting installation..."
    echo ""

    # Execute installation steps
    configure_asterisk_prometheus
    configure_asterisk_http
    configure_asterisk_logging
    restart_asterisk
    install_grafana_alloy
    install_enhanced_monitoring
    configure_grafana_alloy
    start_grafana_alloy

    echo ""
    verify_installation
    echo ""
    show_post_install_info
}

# Run main installation
main