# -*- coding: utf-8 -*-
"""
REAL OCCUPANCY DETECTION SYSTEM
Using Actual WiFi and Bluetooth Hardware
"""

import subprocess
import re
import time
import csv
from datetime import datetime
import os
import platform
import matplotlib.pyplot as plt
import numpy as np
import warnings

# ============================================
# CONFIGURATION - CHANGE THIS ONE LINE!
# ============================================
USE_REAL_HARDWARE = True  # False = Simulation, True = Real Hardware
# ============================================

# Suppress pywifi errors
warnings.filterwarnings("ignore")
import logging
logging.getLogger("pywifi").setLevel(logging.ERROR)

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

class RealHardwareScanner:
    """Actual hardware scanner using system commands"""
    
    def __init__(self):
        self.os_type = platform.system()
        self.check_requirements()
    
    def check_requirements(self):
        """Check if required tools are installed"""
        if self.os_type == "Windows":
            try:
                import pywifi
                import comtypes
                # Suppress pywifi output
                pywifi.set_loglevel(0)  # 0 = ERROR only
                print("✅ Windows WiFi libraries found")
            except ImportError:
                print("⚠️  Install Windows libraries:")
                print("   pip install pywifi comtypes")
                raise SystemExit("Missing required libraries")
    
    def scan_wifi_real(self):
        """Real WiFi scan using pywifi on Windows with retry logic"""
        devices = []
        for attempt in range(3):  # Try 3 times
            try:
                import pywifi
                pywifi.set_loglevel(0)  # Suppress errors
                wifi = pywifi.PyWiFi()
                iface = wifi.interfaces()[0]
                iface.scan()
                time.sleep(3)  # Wait 10 seconds for scan to complete
                results = iface.scan_results()
                
                for result in results:
                    devices.append({
                        'mac': result.bssid,
                        'signal': result.signal,
                        'type': 'WiFi'
                    })
                break  # Success, exit retry loop
                
            except Exception as e:
                if attempt < 2:  # Don't print on last attempt
                    print(f"⏳ WiFi scanning... (attempt {attempt+1}/3)")
                time.sleep(2)  # Wait before retry
                continue
        
        return devices
    
    def scan_bluetooth_real(self):
        """Real Bluetooth scan using multiple methods"""
        devices = []
        
        # Method 1: Try bleak (BLE devices)
        try:
            import asyncio
            from bleak import BleakScanner
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            scanned_devices = loop.run_until_complete(BleakScanner.discover(timeout=10))
            
            for device in scanned_devices:
                if device.address and device.name:
                    devices.append({
                        'mac': device.address,
                        'name': device.name,
                        'type': 'Bluetooth'
                    })
            loop.close()
            
            if devices:
                return devices  # Return if devices found
                
        except Exception as e:
            pass  # Silent fail
        
        # Method 2: Try PowerShell (discoverable devices)
        try:
            cmd = 'powershell -command "Get-WmiObject -Namespace root\\wmi -Class MSFT_BluetoothDevice | Select-Object Name, Address"'
            output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
            
            for line in output.split('\n'):
                if line.strip() and not line.startswith('Name'):
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        name = ' '.join(parts[:-1])
                        mac = parts[-1]
                        if mac and ':' in mac:
                            devices.append({
                                'mac': mac,
                                'name': name,
                                'type': 'Bluetooth'
                            })
        except:
            pass
        
        return devices
    
class SimulatedHardwareScanner:
    """Simulated scanner for testing without hardware"""
    
    def scan_wifi_real(self):
        """Simulated WiFi scan"""
        import random
        devices = []
        num_devices = random.randint(2, 10)
        for i in range(num_devices):
            devices.append({
                'mac': f'AA:BB:CC:DD:EE:{i:02X}',
                'signal': random.randint(30, 80),
                'type': 'WiFi'
            })
        return devices
    
    def scan_bluetooth_real(self):
        """Simulated Bluetooth scan"""
        import random
        devices = []
        num_devices = random.randint(0, 5)
        device_names = ['iPhone', 'Samsung', 'Xiaomi', 'Sony', 'OnePlus', 
                       'Google Pixel', 'AirPods', 'Bose', 'JBL']
        for i in range(num_devices):
            devices.append({
                'mac': f'11:22:33:44:55:{i:02X}',
                'name': random.choice(device_names) + f"_{i+1}",
                'type': 'Bluetooth'
            })
        return devices

class OccupancyMonitor:
    """Main occupancy monitor"""
    
    def __init__(self, use_real=True):
        if use_real:
            self.scanner = RealHardwareScanner()
            print("✅ Using REAL hardware")
        else:
            self.scanner = SimulatedHardwareScanner()
            print("🔄 Using SIMULATION mode")
        
        self.previous_wifi = {}
        self.previous_bt = {}
        self.movement_threshold = 15
        
    def get_color_for_status(self, status):
        """Return color based on occupancy status"""
        color_map = {
            "HIGH_TRAFFIC": Colors.RED,
            "MEDIUM_TRAFFIC": Colors.YELLOW,
            "OCCUPIED": Colors.CYAN,
            "LOW_OCCUPANCY": Colors.GREEN,
            "EMPTY": Colors.BLUE
        }
        return color_map.get(status, Colors.END)
    
    def get_color_for_signal(self, signal):
        """Return color based on signal strength"""
        if signal >= -50:
            return Colors.GREEN  # Excellent
        elif signal >= -60:
            return Colors.CYAN   # Good
        elif signal >= -70:
            return Colors.YELLOW # Fair
        else:
            return Colors.RED    # Poor
    
    def scan(self):
        """Perform scan using selected mode"""
        
        # Get devices
        wifi_devices = self.scanner.scan_wifi_real()
        bt_devices = self.scanner.scan_bluetooth_real()
        
        # Calculate WiFi changes
        wifi_changes = 0
        current_wifi = {d['mac']: d['signal'] for d in wifi_devices}
        
        for mac, signal in current_wifi.items():
            if mac in self.previous_wifi:
                diff = abs(signal - self.previous_wifi[mac])
                if diff > self.movement_threshold:
                    wifi_changes += 1
            else:
                wifi_changes += 1
        
        self.previous_wifi = current_wifi
        
        # Calculate Bluetooth changes
        bt_changes = 0
        current_bt = {d['mac']: d['name'] for d in bt_devices}
        
        for mac in current_bt:
            if mac not in self.previous_bt:
                bt_changes += 1
        
        for mac in self.previous_bt:
            if mac not in current_bt:
                bt_changes += 1
        
        self.previous_bt = current_bt
        
        # Calculate metrics
        total_wifi = len(wifi_devices)
        total_bt = len(bt_devices)
        total_devices = total_wifi + total_bt
        
        # Estimate people
        estimated_people = max(1, total_devices // 2) if total_devices > 0 else 0
        estimated_people = min(estimated_people, 20)
        
        # Movement score
        if total_devices > 0:
            movement = ((wifi_changes * 2 + bt_changes) / (total_devices + 1)) * 100
        else:
            movement = 0
        
        movement = min(100, movement)
        
        # Get device names
        bt_names = [d['name'] for d in bt_devices if d.get('name')]
        
        # Average WiFi signal
        wifi_signals = [d['signal'] for d in wifi_devices if 'signal' in d]
        avg_signal = sum(wifi_signals) / len(wifi_signals) if wifi_signals else -60
        
        status = self.get_status(estimated_people, movement)
        
        return {
            'time': datetime.now().strftime('%H:%M:%S'),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'people': estimated_people,
            'wifi': total_wifi,
            'bt': total_bt,
            'bt_names': bt_names[:5],
            'wifi_signal': round(avg_signal, 1),
            'movement': round(movement, 1),
            'status': status,
            'wifi_changes': wifi_changes,
            'bt_changes': bt_changes,
            'status_color': self.get_color_for_status(status),
            'signal_color': self.get_color_for_signal(avg_signal)
        }
    
    def get_status(self, people, movement):
        """Classify occupancy"""
        if movement > 40 and people > 5:
            return "HIGH_TRAFFIC"
        elif movement > 25 or people > 8:
            return "MEDIUM_TRAFFIC"
        elif people > 2:
            return "OCCUPIED"
        elif people > 0:
            return "LOW_OCCUPANCY"
        else:
            return "EMPTY"

def create_plots(data, session_dir, session_end_time):
    """Create and save 3 plots"""
    
    if not data or len(data) < 2:
        print("⚠️  Not enough data to create plots")
        return
    
    # Extract data
    times = [d['timestamp'] for d in data]
    people = [d['people'] for d in data]
    wifi_signal = [d['wifi_signal'] for d in data]
    wifi_changes = [d['wifi_changes'] for d in data]
    bt_changes = [d['bt_changes'] for d in data]
    movement = [d['movement'] for d in data]
    
    # Create figure with 3 subplots
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))
    fig.suptitle(f'Occupancy & Traffic Analysis\nSession: {session_end_time}', 
                 fontsize=16, fontweight='bold')
    
    # Plot 1: Number of People (no emojis)
    axes[0].plot(range(len(times)), people, 'b-', linewidth=2, marker='o', markersize=4)
    axes[0].fill_between(range(len(times)), 0, people, alpha=0.3, color='blue')
    axes[0].set_title('Number of People Over Time', fontsize=14, fontweight='bold')
    axes[0].set_ylabel('People Count')
    axes[0].grid(True, alpha=0.3)
    axes[0].set_xlabel('Sample Number')
    axes[0].axhline(y=5, color='g', linestyle='--', alpha=0.5, label='Low occupancy')
    axes[0].axhline(y=10, color='y', linestyle='--', alpha=0.5, label='Medium occupancy')
    axes[0].axhline(y=15, color='r', linestyle='--', alpha=0.5, label='High occupancy')
    axes[0].legend()
    
    # Plot 2: WiFi Signal and Changes (no emojis)
    axes[1].plot(range(len(times)), wifi_signal, 'g-', linewidth=2, marker='s', markersize=4, label='Signal Strength')
    axes[1].fill_between(range(len(times)), min(wifi_signal)-5, wifi_signal, alpha=0.3, color='green')
    axes[1].set_title('WiFi Signal & Changes', fontsize=14, fontweight='bold')
    axes[1].set_ylabel('Signal Strength (dBm)', color='g')
    axes[1].grid(True, alpha=0.3)
    axes[1].axhline(y=-50, color='r', linestyle='--', alpha=0.5, label='Weak signal')
    axes[1].set_xlabel('Sample Number')
    
    # Add WiFi changes as bar chart on secondary y-axis
    ax1b = axes[1].twinx()
    ax1b.bar(range(len(times)), wifi_changes, alpha=0.3, color='orange', width=0.5, label='WiFi Changes')
    ax1b.set_ylabel('WiFi Changes', color='orange')
    ax1b.tick_params(axis='y', labelcolor='orange')
    
    # Plot 3: Movement and Bluetooth Changes (no emojis)
    axes[2].plot(range(len(times)), movement, 'r-', linewidth=2, marker='^', markersize=4, label='Movement %')
    axes[2].fill_between(range(len(times)), 0, movement, alpha=0.3, color='red')
    axes[2].set_title('Movement & Bluetooth Changes', fontsize=14, fontweight='bold')
    axes[2].set_ylabel('Movement %', color='r')
    axes[2].grid(True, alpha=0.3)
    axes[2].set_xlabel('Sample Number')
    axes[2].axhline(y=40, color='red', linestyle='--', alpha=0.5, label='High threshold')
    axes[2].axhline(y=25, color='orange', linestyle='--', alpha=0.5, label='Medium threshold')
    
    # Add Bluetooth changes as bar chart
    ax2b = axes[2].twinx()
    ax2b.bar(range(len(times)), bt_changes, alpha=0.3, color='blue', width=0.5, label='BT Changes')
    ax2b.set_ylabel('BT Changes', color='blue')
    ax2b.tick_params(axis='y', labelcolor='blue')
    
    # Add legends
    axes[2].legend(loc='upper left')
    ax2b.legend(loc='upper right')
    
    plt.tight_layout()
    
    # Save plot
    plot_filename = os.path.join(session_dir, f'occupancy_plots_{session_end_time}.png')
    plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
    print(f"✅ Plots saved: {plot_filename}")
    
    plt.close()  # Close the figure to free memory
    
    return plot_filename

def main():
    """Main program loop"""
    print("=" * 70)
    print(Colors.BOLD + "OCCUPANCY & TRAFFIC MONITOR" + Colors.END)
    print("=" * 70)
    
    # Initialize monitor
    monitor = OccupancyMonitor(use_real=USE_REAL_HARDWARE)
    
    print("\nScanning every 10 seconds...")
    print("Press Ctrl+C to stop\n")
    
    data = []
    session_start = datetime.now()
    session_dir = f"session_{session_start.strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(session_dir, exist_ok=True)
    print(f"Session folder: {session_dir}/\n")
    
    # Create single CSV file for this session
    csv_file = os.path.join(session_dir, f'traffic_data_{session_start.strftime("%Y%m%d_%H%M%S")}.csv')
    file_exists = os.path.isfile(csv_file)
    
    try:
        while True:
            result = monitor.scan()
            data.append(result)
            
            # Color-coded display
            status_color = result['status_color']
            signal_color = result['signal_color']
            
            print(f"{Colors.BOLD}Time:{Colors.END} {result['time']}")
            print(f"{Colors.BOLD}People:{Colors.END} {result['people']:2d} (estimated)")
            print(f"{Colors.BOLD}WiFi:{Colors.END} {result['wifi']:2d} | {Colors.BOLD}BT:{Colors.END} {result['bt']:2d}")
            if result['bt_names']:
                print(f"   BT Devices: {', '.join(result['bt_names'][:3])}")
            print(f"{Colors.BOLD}Signal:{Colors.END} {signal_color}{result['wifi_signal']:.1f} dBm{Colors.END}")
            print(f"{Colors.BOLD}Movement:{Colors.END} {result['movement']:.1f}%")
            print(f"{Colors.BOLD}Status:{Colors.END} {status_color}{result['status']}{Colors.END}")
            print("-" * 50)
            
            # Append to single CSV file continuously
            with open(csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['timestamp', 'time', 'people', 'wifi', 
                                                       'bt', 'bt_names', 'wifi_signal', 'movement', 
                                                       'status', 'wifi_changes', 'bt_changes'])
                # Write header only if file is new
                if not file_exists:
                    writer.writeheader()
                    file_exists = True
                row_copy = result.copy()
                # Remove color fields before saving to CSV
                row_copy.pop('signal_color', None)
                row_copy.pop('status_color', None)
                row_copy['bt_names'] = '; '.join(result['bt_names'])
                writer.writerow(row_copy)
            
            time.sleep(3)
            
    except KeyboardInterrupt:
        print("\n\n" + "=" * 70)
        print(Colors.BOLD + "MONITOR STOPPED" + Colors.END)
        print("=" * 70)
        
        session_end = datetime.now()
        session_end_time = session_end.strftime('%Y%m%d_%H%M%S')
        
        # Calculate runtime
        total_seconds = int((session_end - session_start).total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        
        print(f"\nSession Summary:")
        print(f"  - Duration: {minutes}m {seconds}s")
        print(f"  - Total samples: {len(data)}")
        
        if data:
            people_vals = [d['people'] for d in data]
            movement_vals = [d['movement'] for d in data]
            
            print(f"\nStatistics:")
            print(f"  - Avg people: {sum(people_vals)/len(people_vals):.1f}")
            print(f"  - Peak people: {max(people_vals)}")
            print(f"  - Avg movement: {sum(movement_vals)/len(movement_vals):.1f}%")
            print(f"  - Peak movement: {max(movement_vals):.1f}%")
        
        print(f"\nData saved: {csv_file}")
        
        # Create plots
        print("\nGenerating plots...")
        plot_file = create_plots(data, session_dir, session_end_time)
        
        print("\n" + "=" * 70)
        print(Colors.BOLD + "SESSION COMPLETE" + Colors.END)
        print("=" * 70)
        print(f"\nAll files saved in: {session_dir}/")
        print(f"   Data: {os.path.basename(csv_file)}")
        if plot_file:
            print(f"   Plots: {os.path.basename(plot_file)}")
        print("\nProject completed successfully!")
        print("=" * 70)

if __name__ == "__main__":
    main()