# -*- coding: utf-8 -*-
"""
Created on Wed Jun 24 22:53:38 2026

@author: Muhammad Masood Saleem (Data Science & AI , NED University)
"""
import random, math, time, csv
from datetime import datetime
import os
import matplotlib.pyplot as plt
import numpy as np

class TrafficMonitor:
    def __init__(self):
        self.history = []
        self.base_occupancy = 0
        
    def scan(self):
        """Simulate one scan cycle"""
        now = datetime.now()
        hour = now.hour
        
        # Realistic patterns
        if 8 <= hour <= 10:  # Morning rush
            people = random.randint(5, 15)
            movement = random.randint(30, 60)
        elif 12 <= hour <= 14:  # Lunch
            people = random.randint(8, 20)
            movement = random.randint(40, 70)
        elif 17 <= hour <= 19:  # Evening rush
            people = random.randint(10, 18)
            movement = random.randint(35, 65)
        elif 22 <= hour or hour <= 6:  # Night
            people = random.randint(0, 3)
            movement = random.randint(0, 10)
        else:  # Normal hours
            people = random.randint(2, 10)
            movement = random.randint(10, 40)
        
        # Add noise
        people = max(0, people + random.randint(-2, 2))
        movement = max(0, min(100, movement + random.randint(-5, 5)))
        
        # Generate devices
        wifi = max(0, people + random.randint(-1, 2))
        bt = max(0, int(people * 0.6) + random.randint(-1, 1))
        
        # Generate random device names for Bluetooth
        bt_names = []
        for i in range(bt):
            devices = ['iPhone', 'Samsung', 'Xiaomi', 'Sony', 'OnePlus', 'Google Pixel', 
                      'Nothing', 'Realme', 'Vivo', 'Oppo', 'iPad', 'MacBook', 
                      'AirPods', 'Bose', 'Sennheiser', 'JBL', 'Sony WH', 'Samsung Buds']
            bt_names.append(random.choice(devices) + f"_{i+1}")
        
        return {
            'time': now.strftime('%H:%M:%S'),
            'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
            'people': people,
            'wifi': wifi,
            'bt': bt,
            'bt_names': bt_names,
            'wifi_signal': -30 - (people * 1.5) + random.gauss(0, 5),  # Simulated WiFi signal
            'movement': movement,
            'status': self.get_status(people, movement)
        }
    
    def get_status(self, people, movement):
        """Clean status without emojis"""
        if movement > 40:
            return "HIGH_TRAFFIC"
        elif movement > 25:
            return "MEDIUM_TRAFFIC"
        elif people > 2:
            return "OCCUPIED"
        elif people > 0:
            return "LOW_OCCUPANCY"
        else:
            return "EMPTY"
    
    def get_status_display(self, people, movement):
        """Status with emojis for display"""
        if movement > 40:
            return "🔴 HIGH TRAFFIC"
        elif movement > 25:
            return "🟡 MEDIUM TRAFFIC"
        elif people > 2:
            return "🟠 OCCUPIED"
        elif people > 0:
            return "🔵 LOW"
        else:
            return "⚪ EMPTY"
    
    def display_meter(self, movement):
        """Display traffic intensity meter"""
        filled = int(movement / 5)
        bar = '█' * filled + '░' * (20 - filled)
        
        if movement > 40:
            color = '\033[91m'
        elif movement > 25:
            color = '\033[93m'
        elif movement > 10:
            color = '\033[92m'
        else:
            color = '\033[90m'
        
        return f"{color}{bar}\033[0m"

def create_plots(data, session_dir, session_end_time, total_time):
    """Create and save 3 plots"""
    
    if not data:
        print("No data to plot")
        return
    
    # Extract data
    times = [d['timestamp'] for d in data]
    people = [d['people'] for d in data]
    wifi_signal = [d['wifi_signal'] for d in data]
    bt_count = [d['bt'] for d in data]
    
    # Create figure with 3 subplots
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))
    fig.suptitle(f'Occupancy & Traffic Analysis\nSession: {session_end_time} | Duration: {total_time}', 
                 fontsize=16, fontweight='bold')
    
    # Plot 1: Number of People
    axes[0].plot(times, people, 'b-', linewidth=2, marker='o', markersize=4)
    axes[0].fill_between(range(len(times)), 0, people, alpha=0.3, color='blue')
    axes[0].set_title('👥 Number of People Over Time', fontsize=14, fontweight='bold')
    axes[0].set_ylabel('People Count')
    axes[0].grid(True, alpha=0.3)
    axes[0].set_xlabel('Time')
    axes[0].axhline(y=5, color='g', linestyle='--', alpha=0.5, label='Low occupancy')
    axes[0].axhline(y=10, color='y', linestyle='--', alpha=0.5, label='Medium occupancy')
    axes[0].axhline(y=15, color='r', linestyle='--', alpha=0.5, label='High occupancy')
    axes[0].legend()
    
    # Plot 2: WiFi Signal Fluctuations
    axes[1].plot(times, wifi_signal, 'g-', linewidth=2, marker='s', markersize=4)
    axes[1].fill_between(range(len(times)), min(wifi_signal)-5, wifi_signal, alpha=0.3, color='green')
    axes[1].set_title('📶 WiFi Signal Fluctuations', fontsize=14, fontweight='bold')
    axes[1].set_ylabel('Signal Strength (dBm)')
    axes[1].grid(True, alpha=0.3)
    axes[1].set_xlabel('Time')
    axes[1].axhline(y=-50, color='r', linestyle='--', alpha=0.5, label='Weak signal')
    axes[1].axhline(y=-70, color='y', linestyle='--', alpha=0.5, label='Poor signal')
    axes[1].legend()
    
    # Plot 3: Bluetooth Devices with Names
    # Create a scatter plot for BT devices
    bt_times = []
    bt_names = []
    bt_colors = []
    
    color_map = {'iPhone': 'blue', 'Samsung': 'green', 'Xiaomi': 'red', 'Sony': 'purple',
                 'OnePlus': 'orange', 'Google Pixel': 'gray', 'Nothing': 'black', 
                 'Realme': 'pink', 'Vivo': 'cyan', 'Oppo': 'magenta', 'iPad': 'blue',
                 'MacBook': 'silver', 'AirPods': 'white', 'Bose': 'brown', 
                 'Sennheiser': 'darkgreen', 'JBL': 'orange', 'Sony WH': 'purple',
                 'Samsung Buds': 'navy'}
    
    for i, d in enumerate(data):
        for bt_name in d['bt_names']:
            bt_times.append(i)
            bt_names.append(bt_name)
            # Get color for device type
            device_type = bt_name.split('_')[0]
            bt_colors.append(color_map.get(device_type, 'gray'))
    
    if bt_times:
        # Create a scatter plot
        scatter = axes[2].scatter(bt_times, [1]*len(bt_times), 
                                 c=bt_colors, s=100, alpha=0.7, edgecolors='black', linewidth=0.5)
        
        # Add labels for some devices (to avoid overcrowding)
        unique_devices = list(set(bt_names))
        for i, (t, name) in enumerate(zip(bt_times, bt_names)):
            if name in unique_devices[:10]:  # Show only first 10 unique devices
                axes[2].annotate(name, (t, 1.05), fontsize=7, rotation=45, ha='right')
        
        axes[2].set_title('🔵 Bluetooth Devices Detected', fontsize=14, fontweight='bold')
        axes[2].set_ylabel('Devices')
        axes[2].set_xlabel('Time')
        axes[2].set_yticks([])  # Remove y-axis ticks
        axes[2].set_ylim(0.5, 1.5)
        axes[2].grid(True, alpha=0.2)
        
        # Add device count annotation
        for i, d in enumerate(data):
            if d['bt'] > 0:
                axes[2].annotate(f'{d["bt"]} devices', (i, 1.2), fontsize=8, ha='center')
    
    # Rotate x-axis labels for better readability
    for ax in axes:
        ax.tick_params(axis='x', rotation=45)
        # Show only every 10th time label
        if len(times) > 20:
            step = max(1, len(times) // 20)
            for i, label in enumerate(ax.get_xticklabels()):
                if i % step != 0:
                    label.set_visible(False)
    
    # Adjust layout
    plt.tight_layout()
    
    # Save plot
    plot_filename = os.path.join(session_dir, f'occupancy_plots_{session_end_time}.png')
    plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
    print(f"✅ Plots saved: {plot_filename}")
    
    # Show plot (optional - comment out if not needed)
    plt.show()
    
    return plot_filename

def save_data_to_csv(data, session_dir, session_end_time):
    """Save data to CSV file"""
    if not data:
        return None
    
    csv_filename = os.path.join(session_dir, f'traffic_data_{session_end_time}.csv')
    
    with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['timestamp', 'time', 'people', 'wifi', 
                                               'bt', 'bt_names', 'wifi_signal', 'movement', 'status'])
        writer.writeheader()
        # Convert bt_names list to string for CSV
        for row in data:
            row_copy = row.copy()
            row_copy['bt_names'] = '; '.join(row['bt_names'])
            writer.writerow(row_copy)
    
    print(f"✅ Data saved: {csv_filename}")
    return csv_filename

def main():
    """Main program loop"""
    print("=" * 70)
    print("📡 OCCUPANCY & TRAFFIC MONITOR")
    print("Real-time scanning with WiFi/Bluetooth sensors")
    print("=" * 70)
    print("\n🔄 Scanning every 5 seconds...")
    print("⏹️  Press Ctrl+C to stop\n")
    
    monitor = TrafficMonitor()
    data = []
    
    # Create session directory
    session_start = datetime.now()
    session_dir = f"session_{session_start.strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(session_dir, exist_ok=True)
    print(f"📁 Session folder: {session_dir}/\n")
    
    try:
        while True:
            # Scan
            result = monitor.scan()
            data.append(result)
            
            # Display with emojis
            print(f"⏰ {result['time']}")
            print(f"👤 People: {result['people']:2d}")
            print(f"📶 WiFi: {result['wifi']:2d} | Bluetooth: {result['bt']:2d}")
            if result['bt_names']:
                print(f"   BT Devices: {', '.join(result['bt_names'][:3])}" + 
                      (f" +{len(result['bt_names'])-3} more" if len(result['bt_names']) > 3 else ""))
            print(f"📶 WiFi Signal: {result['wifi_signal']:.1f} dBm")
            print(f"🚶 Movement: {result['movement']:3d}%")
            print(f"📊 Traffic: {monitor.display_meter(result['movement'])}")
            print(f"📌 Status: {monitor.get_status_display(result['people'], result['movement'])}")
            print("-" * 50)
            
            # Auto-save every 10 samples
            if len(data) % 10 == 0:
                save_data_to_csv(data, session_dir, 
                               datetime.now().strftime('%Y%m%d_%H%M%S'))
            
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\n" + "=" * 70)
        print("⏹️  MONITOR STOPPED")
        print("=" * 70)
        
        # Calculate session stats
        session_end = datetime.now()
        total_time = session_end - session_start
        total_seconds = int(total_time.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        total_time_str = f"{minutes}m {seconds}s"
        session_end_time = session_end.strftime('%Y%m%d_%H%M%S')
        
        print(f"\n📊 Session Summary:")
        print(f"  - Session ID: {session_dir}")
        print(f"  - Start time: {session_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  - End time: {session_end.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  - Total duration: {total_time_str}")
        print(f"  - Total samples: {len(data)}")
        
        if data:
            # Statistics
            people_vals = [d['people'] for d in data]
            movement_vals = [d['movement'] for d in data]
            wifi_vals = [d['wifi_signal'] for d in data]
            bt_vals = [d['bt'] for d in data]
            
            print(f"\n📈 Statistics:")
            print(f"  - Avg people: {sum(people_vals)/len(people_vals):.1f}")
            print(f"  - Peak people: {max(people_vals)}")
            print(f"  - Avg movement: {sum(movement_vals)/len(movement_vals):.1f}%")
            print(f"  - Peak movement: {max(movement_vals):.1f}%")
            print(f"  - Avg WiFi signal: {sum(wifi_vals)/len(wifi_vals):.1f} dBm")
            print(f"  - Avg BT devices: {sum(bt_vals)/len(bt_vals):.1f}")
            
            # Count status distribution
            from collections import Counter
            status_counts = Counter(d['status'] for d in data)
            print(f"\n  - Occupancy distribution:")
            for status, count in status_counts.most_common():
                print(f"    * {status}: {count} ({count/len(data)*100:.1f}%)")
        
        # Save final data
        print("\n💾 Saving final data...")
        csv_file = save_data_to_csv(data, session_dir, session_end_time)
        
        # Create plots
        print("\n📊 Generating plots...")
        plot_file = create_plots(data, session_dir, session_end_time, total_time_str)
        
        print("\n" + "=" * 70)
        print("✅ SESSION COMPLETE")
        print("=" * 70)
        print(f"\n📁 All files saved in: {session_dir}/")
        if csv_file:
            print(f"   📄 Data: {os.path.basename(csv_file)}")
        if plot_file:
            print(f"   📊 Plots: {os.path.basename(plot_file)}")
        print("\n🎓 Project completed successfully!")
        print("=" * 70)

if __name__ == "__main__":
    main()