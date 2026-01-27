#!/usr/bin/env python3
"""
Combined Allstar Linux Metrics Collector
Combines all metric collectors into a single HTTP endpoint for Prometheus scraping
"""

import time
import json
import sys
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

# Import our collectors
sys.path.append('/home/kj4kpy/allstar-monitoring')
from rpt_metrics import RPTMetricsCollector
from iax2_metrics import IAX2MetricsCollector
from allmon3_metrics import Allmon3WebSocketCollector
from log_metrics import AsteriskLogMetricsCollector

class AllstarMetricsHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.collectors = {
            'rpt': RPTMetricsCollector(),
            'iax2': IAX2MetricsCollector(),
            'allmon3': Allmon3WebSocketCollector(),
            'logs': AsteriskLogMetricsCollector()
        }
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests for metrics"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/metrics':
            self.serve_metrics()
        elif parsed_path.path == '/health':
            self.serve_health()
        else:
            self.send_error(404)
    
    def serve_health(self):
        """Serve health check endpoint"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        health_status = {
            'status': 'healthy',
            'timestamp': int(time.time()),
            'collectors': list(self.collectors.keys())
        }
        
        self.wfile.write(json.dumps(health_status).encode('utf-8'))
    
    def serve_metrics(self):
        """Collect and serve all metrics in Prometheus format"""
        try:
            all_metrics = []
            
            # Collect RPT metrics
            try:
                rpt_metrics = self.collectors['rpt'].collect_all_metrics()
                rpt_prometheus = self.collectors['rpt'].to_prometheus_format(rpt_metrics)
                if rpt_prometheus.strip():
                    all_metrics.append("# RPT Metrics")
                    all_metrics.append(rpt_prometheus)
            except Exception as e:
                print(f"Error collecting RPT metrics: {e}")
                traceback.print_exc()
            
            # Collect IAX2 metrics
            try:
                iax2_metrics = self.collectors['iax2'].collect_all_metrics()
                iax2_prometheus = self.collectors['iax2'].to_prometheus_format(iax2_metrics)
                if iax2_prometheus.strip():
                    all_metrics.append("# IAX2 Enhanced Metrics")
                    all_metrics.append(iax2_prometheus)
            except Exception as e:
                print(f"Error collecting IAX2 metrics: {e}")
                traceback.print_exc()
            
            # Collect Allmon3 metrics
            try:
                allmon3_metrics = self.collectors['allmon3'].collect_sync()
                allmon3_prometheus = self.collectors['allmon3'].to_prometheus_format(allmon3_metrics)
                if allmon3_prometheus.strip():
                    all_metrics.append("# Allmon3 WebSocket Metrics")
                    all_metrics.append(allmon3_prometheus)
            except Exception as e:
                print(f"Error collecting Allmon3 metrics: {e}")
                traceback.print_exc()
            
            # Collect log-based metrics
            try:
                log_metrics = self.collectors['logs'].collect_all_metrics()
                log_prometheus = self.collectors['logs'].to_prometheus_format(log_metrics)
                if log_prometheus.strip():
                    all_metrics.append("# Asterisk Log-based Metrics")
                    all_metrics.append(log_prometheus)
            except Exception as e:
                print(f"Error collecting log metrics: {e}")
                traceback.print_exc()
            
            # Add collection timestamp
            timestamp = int(time.time() * 1000)
            all_metrics.append("# Collection Status")
            all_metrics.append(f'allstar_metrics_collection_timestamp{{instance="node592420"}} {timestamp // 1000} {timestamp}')
            all_metrics.append(f'allstar_metrics_collection_success{{instance="node592420"}} 1 {timestamp}')
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; version=0.0.4; charset=utf-8')
            self.end_headers()
            
            response_body = '\n'.join(all_metrics) + '\n'
            self.wfile.write(response_body.encode('utf-8'))
            
        except Exception as e:
            print(f"Error serving metrics: {e}")
            traceback.print_exc()
            
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Error: {str(e)}\n".encode('utf-8'))
    
    def log_message(self, format, *args):
        """Override to reduce log noise"""
        pass

class AllstarMetricsServer:
    def __init__(self, host='0.0.0.0', port=8089):
        self.host = host
        self.port = port
        self.server = None
        self.running = False
    
    def start(self):
        """Start the metrics server"""
        print(f"Starting Allstar metrics server on {self.host}:{self.port}")
        
        self.server = HTTPServer((self.host, self.port), AllstarMetricsHandler)
        self.running = True
        
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down metrics server...")
            self.stop()
    
    def stop(self):
        """Stop the metrics server"""
        if self.server:
            self.running = False
            self.server.shutdown()
            self.server.server_close()

if __name__ == "__main__":
    server = AllstarMetricsServer()
    
    try:
        server.start()
    except Exception as e:
        print(f"Failed to start server: {e}")
        sys.exit(1)