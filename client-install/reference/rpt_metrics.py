#!/usr/bin/env python3
"""
RPT Metrics Collector for Allstar Linux
Collects metrics from 'rpt show stats' and converts to Prometheus format
"""

import re
import time
import subprocess
import json
from typing import Dict, Any, List

class RPTMetricsCollector:
    def __init__(self):
        self.metrics = {}
        
    def run_asterisk_command(self, command: str) -> str:
        """Execute asterisk command and return output"""
        try:
            result = subprocess.run(
                ['sudo', 'asterisk', '-rx', command],
                capture_output=True, text=True, timeout=10
            )
            return result.stdout
        except subprocess.TimeoutExpired:
            return ""
        except Exception:
            return ""
    
    def parse_rpt_stats(self, node: str) -> Dict[str, Any]:
        """Parse RPT stats for a specific node"""
        output = self.run_asterisk_command(f"rpt show stats {node}")
        metrics = {}
        
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Parse various RPT statistics
            if 'Links:' in line:
                links_match = re.search(r'Links:\s*(\d+)', line)
                if links_match:
                    metrics['rpt_links_count'] = int(links_match.group(1))
            
            elif 'Connections:' in line:
                conn_match = re.search(r'Connections:\s*(\d+)', line)
                if conn_match:
                    metrics['rpt_connections_count'] = int(conn_match.group(1))
            
            elif 'TX Timeout:' in line:
                timeout_match = re.search(r'TX Timeout:\s*(\d+)', line)
                if timeout_match:
                    metrics['rpt_tx_timeout_count'] = int(timeout_match.group(1))
            
            elif 'Tot Kerchunks:' in line:
                kerchunk_match = re.search(r'Tot Kerchunks:\s*(\d+)', line)
                if kerchunk_match:
                    metrics['rpt_total_kerchunks'] = int(kerchunk_match.group(1))
            
            elif 'TX Key Ups:' in line:
                keyups_match = re.search(r'TX Key Ups:\s*(\d+)', line)
                if keyups_match:
                    metrics['rpt_tx_keyups'] = int(keyups_match.group(1))
            
            elif 'RX Key Ups:' in line:
                rx_keyups_match = re.search(r'RX Key Ups:\s*(\d+)', line)
                if rx_keyups_match:
                    metrics['rpt_rx_keyups'] = int(rx_keyups_match.group(1))
                    
            elif 'Time Outs:' in line:
                timeouts_match = re.search(r'Time Outs:\s*(\d+)', line)
                if timeouts_match:
                    metrics['rpt_timeouts'] = int(timeouts_match.group(1))
                    
        return metrics
    
    def parse_link_stats(self, node: str) -> List[Dict[str, Any]]:
        """Parse link statistics for a node"""
        output = self.run_asterisk_command(f"rpt lstats {node}")
        links = []
        
        for line in output.split('\n'):
            line = line.strip()
            if not line or line.startswith('RPT') or line.startswith('Link'):
                continue
                
            # Parse link information
            parts = line.split()
            if len(parts) >= 4:
                try:
                    link_info = {
                        'rpt_link_node': parts[0],
                        'rpt_link_status': parts[1],
                        'rpt_link_direction': parts[2],
                        'rpt_link_connected_time': self.parse_time_duration(parts[3]) if len(parts) > 3 else 0
                    }
                    
                    # Add quality metrics if available
                    if len(parts) > 4:
                        link_info['rpt_link_rx_noise'] = self.safe_float(parts[4])
                    if len(parts) > 5:
                        link_info['rpt_link_tx_noise'] = self.safe_float(parts[5])
                        
                    links.append(link_info)
                except (ValueError, IndexError):
                    continue
                    
        return links
    
    def parse_time_duration(self, time_str: str) -> int:
        """Convert time string to seconds"""
        try:
            if ':' in time_str:
                parts = time_str.split(':')
                if len(parts) == 2:  # MM:SS
                    return int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:  # HH:MM:SS
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            return int(time_str)
        except ValueError:
            return 0
    
    def safe_float(self, value: str) -> float:
        """Safely convert string to float"""
        try:
            return float(value)
        except ValueError:
            return 0.0
    
    def get_node_status(self, node: str) -> Dict[str, Any]:
        """Get comprehensive node status"""
        output = self.run_asterisk_command(f"rpt cmd {node} status")
        status_metrics = {}
        
        for line in output.split('\n'):
            line = line.strip()
            if 'System state:' in line:
                state_match = re.search(r'System state:\s*(\d+)', line)
                if state_match:
                    status_metrics['rpt_system_state'] = int(state_match.group(1))
            
            elif 'Telemetry:' in line:
                if 'ENABLED' in line:
                    status_metrics['rpt_telemetry_enabled'] = 1
                else:
                    status_metrics['rpt_telemetry_enabled'] = 0
            
            elif 'Link:' in line:
                if 'ENABLED' in line:
                    status_metrics['rpt_link_enabled'] = 1
                else:
                    status_metrics['rpt_link_enabled'] = 0
                    
            elif 'Autopatch:' in line:
                if 'ENABLED' in line:
                    status_metrics['rpt_autopatch_enabled'] = 1
                else:
                    status_metrics['rpt_autopatch_enabled'] = 0
        
        return status_metrics
    
    def collect_all_metrics(self) -> Dict[str, Any]:
        """Collect all RPT metrics"""
        nodes = ['592420', '1999']  # Your configured nodes
        all_metrics = {}
        
        for node in nodes:
            node_metrics = {}
            
            # Basic RPT stats
            stats = self.parse_rpt_stats(node)
            node_metrics.update(stats)
            
            # Node status
            status = self.get_node_status(node)
            node_metrics.update(status)
            
            # Link statistics
            links = self.parse_link_stats(node)
            node_metrics['rpt_active_links'] = len([l for l in links if l.get('rpt_link_status') == 'CONNECTED'])
            
            # Add individual link metrics
            for i, link in enumerate(links):
                for key, value in link.items():
                    metric_name = f"{key}_link_{i}"
                    node_metrics[metric_name] = value
            
            all_metrics[node] = node_metrics
        
        return all_metrics
    
    def to_prometheus_format(self, metrics: Dict[str, Any]) -> str:
        """Convert metrics to Prometheus format"""
        output = []
        timestamp = int(time.time() * 1000)
        
        for node, node_metrics in metrics.items():
            for metric_name, value in node_metrics.items():
                if isinstance(value, (int, float)):
                    line = f'{metric_name}{{node="{node}",instance="node592420"}} {value} {timestamp}'
                    output.append(line)
                elif isinstance(value, str):
                    # For string values, create an info metric
                    line = f'{metric_name}_info{{node="{node}",instance="node592420",{metric_name}="{value}"}} 1 {timestamp}'
                    output.append(line)
        
        return '\n'.join(output)

if __name__ == "__main__":
    collector = RPTMetricsCollector()
    metrics = collector.collect_all_metrics()
    prometheus_output = collector.to_prometheus_format(metrics)
    print(prometheus_output)