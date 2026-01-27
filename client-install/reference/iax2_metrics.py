#!/usr/bin/env python3
"""
IAX2 Enhanced Metrics Collector for Allstar Linux
Collects detailed IAX2 metrics beyond basic channel counts
"""

import re
import time
import subprocess
import json
from typing import Dict, Any, List

class IAX2MetricsCollector:
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
    
    def parse_iax2_channels(self) -> List[Dict[str, Any]]:
        """Parse IAX2 channel information"""
        output = self.run_asterisk_command("iax2 show channels")
        channels = []
        
        # Skip header lines and parse channel data
        lines = output.split('\n')
        parsing_channels = False
        
        for line in lines:
            line = line.strip()
            if 'Channel' in line and 'Peer' in line:
                parsing_channels = True
                continue
            
            if parsing_channels and line:
                if line.startswith('---') or not line:
                    continue
                
                # Parse channel information
                parts = line.split()
                if len(parts) >= 6:
                    try:
                        channel_info = {
                            'iax2_channel_name': parts[0],
                            'iax2_channel_peer': parts[1],
                            'iax2_channel_username': parts[2],
                            'iax2_channel_id': parts[3],
                            'iax2_channel_state': parts[4],
                            'iax2_channel_lag': self.safe_int(parts[5])
                        }
                        
                        # Additional fields if available
                        if len(parts) > 6:
                            channel_info['iax2_channel_jitter'] = self.safe_float(parts[6])
                        if len(parts) > 7:
                            channel_info['iax2_channel_format'] = parts[7]
                            
                        channels.append(channel_info)
                    except (ValueError, IndexError):
                        continue
        
        return channels
    
    def parse_iax2_peers(self) -> List[Dict[str, Any]]:
        """Parse IAX2 peer information"""
        output = self.run_asterisk_command("iax2 show peers")
        peers = []
        
        lines = output.split('\n')
        parsing_peers = False
        
        for line in lines:
            line = line.strip()
            if 'Name/Username' in line:
                parsing_peers = True
                continue
                
            if parsing_peers and line:
                if line.startswith('---') or 'peers' in line.lower():
                    continue
                
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        peer_info = {
                            'iax2_peer_name': parts[0],
                            'iax2_peer_host': parts[1],
                            'iax2_peer_dynamic': 1 if parts[2].upper() == 'Y' else 0,
                            'iax2_peer_trunk': 1 if parts[3].upper() == 'Y' else 0,
                            'iax2_peer_encryption': 1 if len(parts) > 4 and parts[4].upper() == 'Y' else 0
                        }
                        
                        # Status information
                        if len(parts) > 5:
                            status = parts[5]
                            peer_info['iax2_peer_status'] = 1 if 'OK' in status.upper() else 0
                            
                            # Extract ping time if available
                            ping_match = re.search(r'\((\d+)ms\)', status)
                            if ping_match:
                                peer_info['iax2_peer_ping_ms'] = int(ping_match.group(1))
                        
                        peers.append(peer_info)
                    except (ValueError, IndexError):
                        continue
        
        return peers
    
    def parse_iax2_registry(self) -> List[Dict[str, Any]]:
        """Parse IAX2 registry information"""
        output = self.run_asterisk_command("iax2 show registry")
        registrations = []
        
        lines = output.split('\n')
        parsing_registry = False
        
        for line in lines:
            line = line.strip()
            if 'Host' in line and 'Username' in line:
                parsing_registry = True
                continue
                
            if parsing_registry and line:
                if line.startswith('---') or 'registrations' in line.lower():
                    continue
                
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        reg_info = {
                            'iax2_registry_host': parts[0],
                            'iax2_registry_username': parts[1],
                            'iax2_registry_state': parts[2],
                            'iax2_registry_registered': 1 if parts[2].upper() == 'REGISTERED' else 0
                        }
                        
                        # Next refresh time if available
                        if len(parts) > 3:
                            refresh_str = ' '.join(parts[3:])
                            reg_info['iax2_registry_refresh_info'] = refresh_str
                        
                        registrations.append(reg_info)
                    except (ValueError, IndexError):
                        continue
        
        return registrations
    
    def parse_iax2_netstats(self) -> Dict[str, Any]:
        """Parse IAX2 network statistics"""
        output = self.run_asterisk_command("iax2 show netstats")
        netstats = {}
        
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Parse network statistics
            if 'Packets sent:' in line:
                sent_match = re.search(r'Packets sent:\s*(\d+)', line)
                if sent_match:
                    netstats['iax2_packets_sent'] = int(sent_match.group(1))
            
            elif 'Packets received:' in line:
                recv_match = re.search(r'Packets received:\s*(\d+)', line)
                if recv_match:
                    netstats['iax2_packets_received'] = int(recv_match.group(1))
            
            elif 'Frames dropped:' in line:
                dropped_match = re.search(r'Frames dropped:\s*(\d+)', line)
                if dropped_match:
                    netstats['iax2_frames_dropped'] = int(dropped_match.group(1))
            
            elif 'Jitter buffer overruns:' in line:
                overrun_match = re.search(r'Jitter buffer overruns:\s*(\d+)', line)
                if overrun_match:
                    netstats['iax2_jitter_overruns'] = int(overrun_match.group(1))
            
            elif 'Jitter buffer underruns:' in line:
                underrun_match = re.search(r'Jitter buffer underruns:\s*(\d+)', line)
                if underrun_match:
                    netstats['iax2_jitter_underruns'] = int(underrun_match.group(1))
        
        return netstats
    
    def safe_int(self, value: str) -> int:
        """Safely convert string to int"""
        try:
            return int(value)
        except ValueError:
            return 0
    
    def safe_float(self, value: str) -> float:
        """Safely convert string to float"""
        try:
            return float(value)
        except ValueError:
            return 0.0
    
    def collect_all_metrics(self) -> Dict[str, Any]:
        """Collect all IAX2 metrics"""
        all_metrics = {}
        
        # Channel metrics
        channels = self.parse_iax2_channels()
        all_metrics['iax2_active_channels'] = len(channels)
        
        # Calculate aggregate channel metrics
        if channels:
            total_lag = sum(ch.get('iax2_channel_lag', 0) for ch in channels)
            avg_lag = total_lag / len(channels) if channels else 0
            all_metrics['iax2_avg_channel_lag'] = avg_lag
            
            # Channel states
            state_counts = {}
            for ch in channels:
                state = ch.get('iax2_channel_state', 'unknown')
                state_counts[state] = state_counts.get(state, 0) + 1
            
            for state, count in state_counts.items():
                # Sanitize state name for Prometheus - remove invalid characters
                sanitized_state = re.sub(r'[^a-zA-Z0-9_]', '_', state.lower())
                all_metrics[f'iax2_channels_state_{sanitized_state}'] = count
        
        # Peer metrics
        peers = self.parse_iax2_peers()
        all_metrics['iax2_total_peers'] = len(peers)
        
        if peers:
            online_peers = sum(1 for peer in peers if peer.get('iax2_peer_status', 0) == 1)
            all_metrics['iax2_online_peers'] = online_peers
            all_metrics['iax2_offline_peers'] = len(peers) - online_peers
            
            # Calculate average ping time
            ping_times = [peer.get('iax2_peer_ping_ms', 0) for peer in peers if peer.get('iax2_peer_ping_ms', 0) > 0]
            if ping_times:
                all_metrics['iax2_avg_peer_ping_ms'] = sum(ping_times) / len(ping_times)
        
        # Registry metrics
        registrations = self.parse_iax2_registry()
        all_metrics['iax2_total_registrations'] = len(registrations)
        
        if registrations:
            registered_count = sum(1 for reg in registrations if reg.get('iax2_registry_registered', 0) == 1)
            all_metrics['iax2_active_registrations'] = registered_count
        
        # Network statistics
        netstats = self.parse_iax2_netstats()
        all_metrics.update(netstats)
        
        # Calculate packet loss ratio if data available
        sent = netstats.get('iax2_packets_sent', 0)
        received = netstats.get('iax2_packets_received', 0)
        dropped = netstats.get('iax2_frames_dropped', 0)
        
        if sent > 0:
            all_metrics['iax2_packet_loss_ratio'] = dropped / sent
        
        return all_metrics
    
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
    collector = IAX2MetricsCollector()
    metrics = collector.collect_all_metrics()
    prometheus_output = collector.to_prometheus_format(metrics)
    print(prometheus_output)