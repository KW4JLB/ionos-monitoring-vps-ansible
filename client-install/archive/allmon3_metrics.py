#!/usr/bin/env python3
"""
Allmon3 WebSocket Metrics Collector for Allstar Linux
Connects to allmon3 WebSocket and collects real-time data
"""

import asyncio
import websockets
import json
import time
import signal
import sys
from typing import Dict, Any, Optional

class Allmon3WebSocketCollector:
    def __init__(self, host='127.0.0.1', port=16700, nodes=['592420', '1999']):
        self.host = host
        self.port = port
        self.nodes = nodes
        self.metrics = {}
        self.running = True
        
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.running = False
        
    async def connect_to_node(self, node: str) -> Optional[Dict[str, Any]]:
        """Connect to allmon3 websocket for a specific node"""
        uri = f"ws://{self.host}:{self.port}"
        
        try:
            async with websockets.connect(uri) as websocket:
                # Subscribe to node updates
                subscribe_msg = {
                    "command": "subscribe",
                    "node": node
                }
                await websocket.send(json.dumps(subscribe_msg))
                
                # Wait for response
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                
                return data
                
        except asyncio.TimeoutError:
            print(f"Timeout connecting to node {node}")
            return None
        except websockets.exceptions.ConnectionClosed:
            print(f"Connection closed for node {node}")
            return None
        except Exception as e:
            print(f"Error connecting to node {node}: {e}")
            return None
    
    async def collect_node_status(self, node: str) -> Dict[str, Any]:
        """Collect status for a specific node"""
        data = await self.connect_to_node(node)
        if not data:
            return {}
            
        metrics = {}
        
        # Parse allmon3 status data
        if isinstance(data, dict):
            # Node connection status
            if 'connected' in data:
                metrics['allmon3_node_connected'] = 1 if data['connected'] else 0
            
            # Links information
            if 'links' in data and isinstance(data['links'], dict):
                links = data['links']
                metrics['allmon3_total_links'] = len(links)
                
                connected_links = 0
                for link_id, link_info in links.items():
                    if isinstance(link_info, dict):
                        if link_info.get('mode') == 'CONNECTED':
                            connected_links += 1
                        
                        # Individual link metrics
                        link_node = link_info.get('node', link_id)
                        link_mode = link_info.get('mode', 'unknown')
                        
                        # Create a normalized link status metric
                        link_status = 1 if link_mode == 'CONNECTED' else 0
                        metrics[f'allmon3_link_status_{link_node}'] = link_status
                        
                        # Link direction
                        direction = link_info.get('direction', 'unknown')
                        metrics[f'allmon3_link_direction_{link_node}'] = 1 if direction == 'OUTBOUND' else 0
                        
                        # Connection time
                        conn_time = link_info.get('connection_time', 0)
                        if isinstance(conn_time, (int, float)):
                            metrics[f'allmon3_link_duration_{link_node}'] = conn_time
                
                metrics['allmon3_connected_links'] = connected_links
            
            # Users information
            if 'users' in data and isinstance(data['users'], dict):
                users = data['users']
                metrics['allmon3_total_users'] = len(users)
                
                active_users = 0
                for user_id, user_info in users.items():
                    if isinstance(user_info, dict) and user_info.get('active', False):
                        active_users += 1
                
                metrics['allmon3_active_users'] = active_users
            
            # System status
            if 'system' in data and isinstance(data['system'], dict):
                system_info = data['system']
                
                # System state
                state = system_info.get('state', 0)
                metrics['allmon3_system_state'] = int(state) if isinstance(state, (int, str)) else 0
                
                # Telemetry status
                telemetry = system_info.get('telemetry', False)
                metrics['allmon3_telemetry_enabled'] = 1 if telemetry else 0
                
                # Linking status
                linking = system_info.get('linking', False)
                metrics['allmon3_linking_enabled'] = 1 if linking else 0
                
                # Autopatch status
                autopatch = system_info.get('autopatch', False)
                metrics['allmon3_autopatch_enabled'] = 1 if autopatch else 0
            
            # Activity metrics
            if 'activity' in data and isinstance(data['activity'], dict):
                activity = data['activity']
                
                # Last keyed time
                last_keyed = activity.get('last_keyed', 0)
                if isinstance(last_keyed, (int, float)):
                    metrics['allmon3_last_keyed_seconds'] = int(time.time()) - int(last_keyed)
                
                # Total keyups
                total_keyups = activity.get('total_keyups', 0)
                metrics['allmon3_total_keyups'] = int(total_keyups) if isinstance(total_keyups, (int, str)) else 0
                
                # Current TX status
                tx_active = activity.get('tx_active', False)
                metrics['allmon3_tx_active'] = 1 if tx_active else 0
        
        return metrics
    
    def parse_simple_status(self, status_text: str, node: str) -> Dict[str, Any]:
        """Parse simple status text format (fallback)"""
        metrics = {}
        
        # Basic parsing for simple status format
        if 'CONNECTED' in status_text:
            metrics['allmon3_node_connected'] = 1
        else:
            metrics['allmon3_node_connected'] = 0
        
        # Count links mentioned in status
        link_count = status_text.count('Link:')
        metrics['allmon3_total_links'] = link_count
        
        return metrics
    
    async def collect_all_metrics(self) -> Dict[str, Any]:
        """Collect metrics from all configured nodes"""
        all_metrics = {}
        
        # Set up signal handling
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        for node in self.nodes:
            if not self.running:
                break
                
            node_metrics = await self.collect_node_status(node)
            if node_metrics:
                # Prefix metrics with node identifier
                for metric_name, value in node_metrics.items():
                    all_metrics[f"{metric_name}"] = value
                    all_metrics[f"{metric_name}_node_{node}"] = value
        
        return all_metrics
    
    def collect_sync(self) -> Dict[str, Any]:
        """Synchronous wrapper for async collection"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self.collect_all_metrics())
        except Exception as e:
            print(f"Error collecting allmon3 metrics: {e}")
            return {}
        finally:
            if loop.is_running():
                loop.close()
    
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
    collector = Allmon3WebSocketCollector()
    metrics = collector.collect_sync()
    prometheus_output = collector.to_prometheus_format(metrics)
    print(prometheus_output)