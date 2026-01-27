#!/usr/bin/env python3
"""
Asterisk Log-based Metrics Collector for Allstar Linux
Parses asterisk logs to extract connection events, authentication failures, and audio quality metrics
"""

import re
import time
import json
import subprocess
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict, deque

class AsteriskLogMetricsCollector:
    def __init__(self, log_files=['/var/log/asterisk/full', '/var/log/asterisk/messages']):
        self.log_files = log_files
        self.metrics = defaultdict(int)
        self.last_positions = {}
        self.event_history = deque(maxlen=1000)  # Keep last 1000 events
        
    def get_file_position(self, filepath: str) -> int:
        """Get current position in log file"""
        return self.last_positions.get(filepath, 0)
    
    def set_file_position(self, filepath: str, position: int):
        """Set current position in log file"""
        self.last_positions[filepath] = position
    
    def parse_log_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single log line and extract relevant information"""
        if not line.strip():
            return None
            
        event = {}
        
        # Extract timestamp
        timestamp_match = re.match(r'\[([^\]]+)\]', line)
        if timestamp_match:
            try:
                timestamp_str = timestamp_match.group(1)
                # Parse Asterisk timestamp format
                event['timestamp'] = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f')
            except ValueError:
                try:
                    # Try alternative format
                    event['timestamp'] = datetime.strptime(timestamp_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    event['timestamp'] = datetime.now()
        else:
            event['timestamp'] = datetime.now()
        
        # IAX2 Connection Events
        if 'IAX2' in line:
            if 'Registered IAX2' in line:
                event['type'] = 'iax2_registration'
                node_match = re.search(r'peer \'(\d+)\'', line)
                if node_match:
                    event['node'] = node_match.group(1)
                    event['event'] = 'registered'
            
            elif 'Unregistered IAX2' in line:
                event['type'] = 'iax2_registration'
                node_match = re.search(r'peer \'(\d+)\'', line)
                if node_match:
                    event['node'] = node_match.group(1)
                    event['event'] = 'unregistered'
            
            elif 'Call accepted by' in line:
                event['type'] = 'iax2_call'
                event['event'] = 'accepted'
                
            elif 'Call rejected by' in line:
                event['type'] = 'iax2_call'
                event['event'] = 'rejected'
                
            elif 'Received mini frame before first full frame' in line:
                event['type'] = 'iax2_error'
                event['event'] = 'mini_frame_error'
                
            elif 'No such context' in line:
                event['type'] = 'iax2_error'
                event['event'] = 'no_context'
        
        # RPT Events
        if 'app_rpt.c' in line or 'rpt' in line.lower():
            if 'Connect attempt to' in line:
                event['type'] = 'rpt_connection'
                event['event'] = 'attempt'
                node_match = re.search(r'to (\d+)', line)
                if node_match:
                    event['target_node'] = node_match.group(1)
            
            elif 'Connected to' in line:
                event['type'] = 'rpt_connection'
                event['event'] = 'connected'
                node_match = re.search(r'to (\d+)', line)
                if node_match:
                    event['target_node'] = node_match.group(1)
            
            elif 'Disconnected from' in line:
                event['type'] = 'rpt_connection'
                event['event'] = 'disconnected'
                node_match = re.search(r'from (\d+)', line)
                if node_match:
                    event['target_node'] = node_match.group(1)
            
            elif 'Timeout timer expired' in line:
                event['type'] = 'rpt_timeout'
                event['event'] = 'tx_timeout'
                
            elif 'Kerchunk' in line:
                event['type'] = 'rpt_activity'
                event['event'] = 'kerchunk'
        
        # Authentication Events
        if 'Failed to authenticate' in line or 'Authentication failed' in line:
            event['type'] = 'authentication'
            event['event'] = 'failed'
            
            # Extract IP address if available
            ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
            if ip_match:
                event['ip_address'] = ip_match.group(1)
        
        # Audio Quality Events
        if 'jitter' in line.lower():
            event['type'] = 'audio_quality'
            event['event'] = 'jitter'
            
            # Extract jitter value
            jitter_match = re.search(r'jitter[:\s]+(\d+)', line, re.IGNORECASE)
            if jitter_match:
                event['jitter_value'] = int(jitter_match.group(1))
        
        if 'frame' in line.lower() and ('drop' in line.lower() or 'lost' in line.lower()):
            event['type'] = 'audio_quality'
            event['event'] = 'frame_drop'
        
        # System Events
        if 'Starting Asterisk' in line:
            event['type'] = 'system'
            event['event'] = 'start'
        elif 'Asterisk ending' in line:
            event['type'] = 'system'
            event['event'] = 'stop'
        elif 'Reloading' in line:
            event['type'] = 'system'
            event['event'] = 'reload'
        
        return event if event.get('type') else None
    
    def read_new_log_entries(self, filepath: str) -> List[str]:
        """Read new entries from log file since last check"""
        try:
            with open(filepath, 'r') as f:
                current_pos = self.get_file_position(filepath)
                f.seek(current_pos)
                
                new_lines = f.readlines()
                new_pos = f.tell()
                self.set_file_position(filepath, new_pos)
                
                return new_lines
        except (IOError, OSError) as e:
            print(f"Error reading log file {filepath}: {e}")
            return []
    
    def process_log_files(self, time_window_minutes: int = 60) -> List[Dict[str, Any]]:
        """Process all log files and return events within time window"""
        all_events = []
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
        
        for log_file in self.log_files:
            try:
                new_lines = self.read_new_log_entries(log_file)
                
                for line in new_lines:
                    event = self.parse_log_line(line)
                    if event and event.get('timestamp', datetime.min) >= cutoff_time:
                        event['log_file'] = log_file
                        all_events.append(event)
                        self.event_history.append(event)
                        
            except Exception as e:
                print(f"Error processing log file {log_file}: {e}")
                continue
        
        return all_events
    
    def calculate_metrics(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate metrics from parsed events"""
        metrics = defaultdict(int)
        
        # Count events by type and subtype
        for event in events:
            event_type = event.get('type', 'unknown')
            event_name = event.get('event', 'unknown')
            
            metrics[f'asterisk_log_events_{event_type}_total'] += 1
            metrics[f'asterisk_log_events_{event_type}_{event_name}'] += 1
            
            # Special handling for specific event types
            if event_type == 'iax2_registration':
                if event_name == 'registered':
                    node = event.get('node', 'unknown')
                    metrics[f'asterisk_log_iax2_registration_success_node_{node}'] += 1
                elif event_name == 'unregistered':
                    node = event.get('node', 'unknown')
                    metrics[f'asterisk_log_iax2_unregistration_node_{node}'] += 1
            
            elif event_type == 'rpt_connection':
                target_node = event.get('target_node', 'unknown')
                if event_name == 'connected':
                    metrics[f'asterisk_log_rpt_connections_success_to_{target_node}'] += 1
                elif event_name == 'disconnected':
                    metrics[f'asterisk_log_rpt_disconnections_from_{target_node}'] += 1
                elif event_name == 'attempt':
                    metrics[f'asterisk_log_rpt_connection_attempts_to_{target_node}'] += 1
            
            elif event_type == 'authentication' and event_name == 'failed':
                ip_addr = event.get('ip_address', 'unknown')
                # Sanitize IP address for metric name - replace dots and special chars
                sanitized_ip = re.sub(r'[^a-zA-Z0-9_]', '_', ip_addr)
                metrics[f'asterisk_log_auth_failures_from_{sanitized_ip}'] += 1
            
            elif event_type == 'audio_quality':
                if event_name == 'jitter' and 'jitter_value' in event:
                    # Track jitter statistics
                    jitter_value = event['jitter_value']
                    metrics['asterisk_log_jitter_events_total'] += 1
                    metrics['asterisk_log_jitter_sum'] += jitter_value
                    
                    # Update max jitter if this is higher
                    current_max = metrics.get('asterisk_log_jitter_max', 0)
                    if jitter_value > current_max:
                        metrics['asterisk_log_jitter_max'] = jitter_value
                
                elif event_name == 'frame_drop':
                    metrics['asterisk_log_frame_drops_total'] += 1
        
        # Calculate rates and averages
        if metrics.get('asterisk_log_jitter_events_total', 0) > 0:
            total_jitter = metrics.get('asterisk_log_jitter_sum', 0)
            jitter_count = metrics['asterisk_log_jitter_events_total']
            metrics['asterisk_log_jitter_avg'] = total_jitter / jitter_count
        
        # Connection success rate
        total_attempts = metrics.get('asterisk_log_events_rpt_connection_attempt', 0)
        successful_connections = metrics.get('asterisk_log_events_rpt_connection_connected', 0)
        
        if total_attempts > 0:
            metrics['asterisk_log_rpt_connection_success_rate'] = successful_connections / total_attempts
        
        return dict(metrics)
    
    def collect_all_metrics(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """Collect all log-based metrics"""
        events = self.process_log_files(time_window_minutes)
        metrics = self.calculate_metrics(events)
        
        # Add some summary statistics
        metrics['asterisk_log_total_events_processed'] = len(events)
        metrics['asterisk_log_collection_timestamp'] = int(time.time())
        
        return metrics
    
    def to_prometheus_format(self, metrics: Dict[str, Any]) -> str:
        """Convert metrics to Prometheus format"""
        output = []
        timestamp = int(time.time() * 1000)
        
        for metric_name, value in metrics.items():
            if isinstance(value, (int, float)):
                line = f'{metric_name}{{instance="node592420"}} {value} {timestamp}'
                output.append(line)
        
        return '\n'.join(output)

if __name__ == "__main__":
    collector = AsteriskLogMetricsCollector()
    metrics = collector.collect_all_metrics()
    prometheus_output = collector.to_prometheus_format(metrics)
    print(prometheus_output)