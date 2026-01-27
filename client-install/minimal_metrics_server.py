#!/usr/bin/env python3
"""
MINIMAL Allstar Metrics Collector - Optimized for Raspberry Pi 3B+
Only collects most critical metrics with longer intervals to reduce system load
"""

import time
import subprocess
import re
from http.server import HTTPServer, BaseHTTPRequestHandler

class MinimalAllstarHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            self.serve_minimal_metrics()
        elif self.path == '/health':
            self.serve_health()
        else:
            self.send_error(404)
    
    def serve_health(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status":"healthy"}')
    
    def serve_minimal_metrics(self):
        """Serve only essential metrics to reduce system load"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        
        metrics = []
        timestamp = int(time.time() * 1000)
        
        try:
            # Only collect basic RPT status - most critical info
            output = subprocess.run(['sudo', '/usr/sbin/asterisk', '-rx', 'rpt stats 592420'], 
                                  capture_output=True, text=True, timeout=5)
            
            active_links = 0
            if output.returncode == 0 and output.stdout:
                for line in output.stdout.split('\n'):
                    if 'Links active:' in line:
                        match = re.search(r'Links active:\s*(\d+)', line)
                        if match:
                            active_links = int(match.group(1))
                            break
            
            metrics.append(f'rpt_active_links{{node="592420",instance="node592420"}} {active_links} {timestamp}')
            metrics.append(f'allstar_metrics_collection_success{{instance="node592420"}} 1 {timestamp}')
            metrics.append(f'allstar_metrics_collection_timestamp{{instance="node592420"}} {timestamp} {timestamp}')
            
        except Exception as e:
            print(f"Error collecting metrics: {e}")
            metrics.append(f'allstar_metrics_collection_success{{instance="node592420"}} 0 {timestamp}')
        
        response = '\n'.join(metrics) + '\n'
        self.wfile.write(response.encode('utf-8'))

def main():
    server = HTTPServer(('0.0.0.0', 8089), MinimalAllstarHandler)
    print("Minimal Allstar Metrics Server running on port 8089...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()

if __name__ == '__main__':
    main()