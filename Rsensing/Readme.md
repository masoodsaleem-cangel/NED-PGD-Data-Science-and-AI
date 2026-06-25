# 📡 Real-Time Occupancy Detection System

## WiFi & Bluetooth Based People Traffic Monitoring

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-blue.svg)]()

---

## 📖 Overview

This project implements a **real-time occupancy and traffic monitoring system** using WiFi and Bluetooth signals as proximity sensors. It detects the presence of people by analyzing WiFi signal strength fluctuations and Bluetooth device detections, creating a comprehensive dataset for occupancy analysis.

**Key Innovation:** Uses WiFi signal **changes (RSSI fluctuations)** rather than just device counting to detect movement and occupancy patterns.

---

## 🎯 Features

### Core Functionality
- **Real-time Monitoring**: Continuous scanning with customizable intervals
- **Dual Sensor Fusion**: Combines WiFi and Bluetooth data
- **Movement Detection**: Tracks signal strength changes to detect people moving
- **Occupancy Classification**: 
  - HIGH_TRAFFIC
  - MEDIUM_TRAFFIC
  - OCCUPIED
  - LOW_OCCUPANCY
  - EMPTY

### Data Management
- **Automatic Dataset Generation**: Saves to CSV in real-time
- **Session Organization**: Each session in timestamped folder
- **Continuous Append**: Single CSV file per session (no duplicates)

### Visualization
- **3 Professional Plots**:
  1. People Count Over Time
  2. WiFi Signal Strength & Changes
  3. Movement & Bluetooth Changes

### User Interface
- **Color-Coded Output**:
  - 🟢 Green: Low occupancy / Excellent signal
  - 🟡 Yellow: Medium traffic / Fair signal
  - 🔴 Red: High traffic / Poor signal
  - 🔵 Blue: Empty
  - 🩵 Cyan: Occupied / Good signal
- **Real-time Status Display**
- **Session Statistics** on completion

---

## 🏗️ System Architecture

### Flow Diagram

┌─────────────────────────────────────────────────────────┐
│ OCCUPANCY DETECTION │
├─────────────────────────────────────────────────────────┤
│ │
│ ┌──────────────┐ ┌──────────────┐ │
│ │ WiFi Scan │ │ BT Scan │ │
│ │ (pywifi) │ │ (bleak) │ │
│ └──────┬───────┘ └──────┬───────┘ │
│ │ │ │
│ └─────────┬─────────┘ │
│ │ │
│ ▼ │
│ ┌──────────────────┐ │
│ │ Signal Analysis │ │
│ │ - RSSI Changes │ │
│ │ - Device Count │ │
│ │ - Movement % │ │
│ └────────┬─────────┘ │
│ │ │
│ ▼ │
│ ┌──────────────────┐ │
│ │ Occupancy │ │
│ │ Classification │ │
│ └────────┬─────────┘ │
│ │ │
│ ┌────────┴────────┐ │
│ │ │ │
│ ▼ ▼ │
│ ┌───────────┐ ┌───────────┐ │
│ │ CSV │ │ Plots │ │
│ │ Dataset │ │ (3 PNG) │ │
│ └───────────┘ └───────────┘ │
│ │
└─────────────────────────────────────────────────────────┘


### Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Language** | Python 3.8+ | Core development |
| **WiFi Scanning** | pywifi, comtypes | Hardware-level WiFi access |
| **Bluetooth Scanning** | bleak, asyncio | BLE device discovery |
| **Data Processing** | CSV, Collections | Dataset management |
| **Visualization** | Matplotlib, NumPy | Plot generation |
| **Session Management** | OS, Datetime | File organization |

---

## 📊 Dataset Structure

### CSV Columns

| Column | Description | Type |
|--------|-------------|------|
| `timestamp` | Full date and time | String |
| `time` | Time only (HH:MM:SS) | String |
| `people` | Estimated number of people | Integer |
| `wifi` | Number of WiFi devices detected | Integer |
| `bt` | Number of Bluetooth devices detected | Integer |
| `bt_names` | Names of detected BT devices | String (semicolon-separated) |
| `wifi_signal` | Average WiFi signal strength (dBm) | Float |
| `movement` | Movement intensity score (%) | Float |
| `status` | Occupancy classification | String |
| `wifi_changes` | Number of WiFi signal changes | Integer |
| `bt_changes` | Number of BT device changes | Integer |

### Occupancy Classifications

| Status | Criteria |
|--------|----------|
| **HIGH_TRAFFIC** | Movement > 40% AND People > 5 |
| **MEDIUM_TRAFFIC** | Movement > 25% OR People > 8 |
| **OCCUPIED** | People > 2 |
| **LOW_OCCUPANCY** | People > 0 |
| **EMPTY** | People = 0 |

---

## 📂 Project Structure
Rsensing/
│
├── Rsense.py # Main application
├── README.md # Project documentation
├── flowchart.txt # System flowchart
├── requirements.txt # Python dependencies
├── LICENSE # MIT License
├── .gitignore # Git ignore rules
│
├── session_YYYYMMDD_HHMMSS/ # Session folders (auto-generated)
│ ├── traffic_data_YYYYMMDD_HHMMSS.csv # Dataset
│ └── occupancy_plots_YYYYMMDD_HHMMSS.png # Visualization
│
└── CONTRIBUTING.md # Contributing guidelines

---

## 🚀 Installation

### Prerequisites

```bash
# Python 3.8 or higher
python --version

# Install required packages
pip install -r requirements.txt

pywifi>=1.1.12
comtypes>=1.1.14
bleak>=0.20.0
matplotlib>=3.5.0
numpy>=1.21.0

Setup

1- Clone the repository
git clone https://github.com/yourusername/occupancy-detection.git
cd occupancy-detection

2-Install dependencies
pip install -r requirements.txt

3- Install Npcap driver (Windows only)

Download from: https://npcap.com/

Install with "WinPcap API-compatible Mode" checked

Restart computer after installation

4- Run as Administrator
python Rsense.py

Controls
Action	Result
Ctrl+C	Stop monitoring, save data, generate plots
Wait	Automatic scanning every 10 seconds

======================================================================
OCCUPANCY & TRAFFIC MONITOR
======================================================================
✅ Windows WiFi libraries found
✅ Using REAL hardware

Scanning every 10 seconds...
Press Ctrl+C to stop

Session folder: session_20260625_160921/

Time: 16:09:32
People:  3 (estimated)
WiFi:  6 | BT:  0
Signal: -70.3 dBm
Movement: 100.0%
Status: MEDIUM_TRAFFIC
--------------------------------------------------

📊 Visualization Outputs
1. People Count Over Time
Tracks occupancy patterns

Color-coded threshold lines (Low/Medium/High)

Area fill for visualization

2. WiFi Signal & Changes
Real-time signal strength monitoring

Signal degradation with occupancy

WiFi changes as bar chart

3. Movement & Bluetooth Changes
Movement intensity tracking

Bluetooth device changes

Threshold indicators

🔧 Configuration
Hardware Mode
python
# In Rsense.py - Line ~16
USE_REAL_HARDWARE = True   # True = Real hardware, False = Simulation

Scanning Intervals
python
# WiFi scan duration - Line ~63
time.sleep(3)   # WiFi scan (seconds)

# Bluetooth scan duration - Line ~88  
timeout=10      # BT scan (seconds)

# Main loop interval - Line ~443
time.sleep(3)   # Wait between cycles

🎓 Educational Value
This project demonstrates:

Sensor Fusion: Combining multiple data sources (WiFi + BT)

Real-time Processing: Continuous data collection and analysis

Signal Processing: RSSI analysis for movement detection

Data Management: Organized storage with timestamps

Data Visualization: Effective representation of occupancy patterns

Pattern Recognition: Identifying occupancy and movement patterns

🛠️ Troubleshooting
Common Issues
Issue	Solution
"Open handle failed!"	Ignore - Windows driver noise, code still works
No Bluetooth devices	Normal - devices must be discoverable
WiFi not scanning	Run as Administrator
Missing libraries	pip install -r requirements.txt
Npcap error	Install Npcap with WinPcap compatibility
🤝 Contributing
Contributions are welcome! Please see CONTRIBUTING.md for details.

📄 License
This project is licensed under the MIT License - see the LICENSE file for details.

👨‍🎓 Author
Your MUhammad Masood Saleem

GitHub: @masoodsaleem-cangel

Email: your.email@example.com

🙏 Acknowledgments
University Project Supervisor
Sir Uzair

NED - Data Science & AI Program

Python Community

Open Source Libraries

📚 References
WiFi-based occupancy detection systems

Bluetooth proximity sensing techniques

RSSI signal processing methods

Real-time data visualization best practices

📝 Changelog
v1.0.0 (June 2026)
Initial release

WiFi and Bluetooth scanning

Real-time monitoring

CSV dataset generation

3 visualization plots

Color-coded output

⭐ Star this repository if you find it useful!

Last Updated: June 2026