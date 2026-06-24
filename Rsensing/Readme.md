# 📡 Occupancy Detection System Using WiFi & Bluetooth Sensors

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Completed-success.svg)]()

## 📖 Project Overview

This project implements a **real-time occupancy and traffic monitoring system** using WiFi and Bluetooth signals as proximity sensors. It detects the presence of people by analyzing WiFi signal fluctuations and Bluetooth device detections, creating a comprehensive dataset for occupancy analysis.

### 🎯 Key Features

- **Real-time Monitoring**: Continuous scanning every 5 seconds
- **Dual Sensor Fusion**: Combines WiFi and Bluetooth data
- **Smart Detection**: 
  - WiFi signal strength analysis
  - Bluetooth device presence detection
  - Movement pattern recognition
  - Occupancy level classification
- **Data Management**:
  - Automatic CSV dataset generation
  - Session-based folder organization
  - Timestamped file naming
- **Visualization**:
  - People count over time
  - WiFi signal fluctuations
  - Bluetooth device detection
- **Professional Output**:
  - Clean CSV format (no emoji corruption)
  - High-resolution PNG plots
  - Detailed session statistics

## 🏗️ System Architecture

### Flowchart
┌─────────────────────────────────────────────┐
│ OCCUPANCY DETECTION SYSTEM │
├─────────────────────────────────────────────┤
│ │
│ [WiFi Sensors] ─┐ │
│ ├──> [Data Collection] │
│ [BT Sensors] ───┘ │
│ │
│ ↓ │
│ ┌─────────────────────────────────┐ │
│ │ Data Processing Pipeline │ │
│ │ - Signal Analysis │ │
│ │ - Movement Detection │ │
│ │ - Occupancy Classification │ │
│ └─────────────────────────────────┘ │
│ ↓ │
│ ┌─────────────────────────────────┐ │
│ │ Output Generation │ │
│ │ - CSV Dataset │ │
│ │ - 3 Visualization Plots │ │
│ │ - Session Statistics │ │
│ └─────────────────────────────────┘ │
│ │
└─────────────────────────────────────────────┘

## 🚀 Installation

### Prerequisites

```bash
# Python 3.8 or higher
python --version

# Install required packages
pip install -r requirements.txt

Dependencies
matplotlib>=3.5.0
numpy>=1.21.0

Setup
Clone the repository

bash
git clone https://github.com/yourusername/occupancy-detection.git
cd occupancy-detection
Install dependencies

bash
pip install -r requirements.txt
Run the application

bash
python main.py

📊 Visualization Outputs
1. People Count Over Time
Shows occupancy patterns

Color-coded threshold lines

Area fill for visualization

2. WiFi Signal Fluctuations
Real-time signal strength monitoring

Signal degradation with occupancy

Quality threshold indicators

3. Bluetooth Devices Detection
Scatter plot of detected devices

Color-coded by device type

Device name annotations

🎓 Educational Value
This project demonstrates:

Sensor Fusion: Combining multiple data sources

Real-time Processing: Continuous data collection and analysis

Data Management: Organized storage with timestamps

Visualization: Effective data representation

Pattern Recognition: Occupancy and movement patterns

🤝 Contributing
Contributions are welcome! Please see CONTRIBUTING.md for details.

📄 License
This project is licensed under the MIT License - see the LICENSE file for details.

👨‍🎓 Author
Your Muhammad Masood Saleem

GitHub: @masoodsaleem-cangel

Email: masoodsaleem@hotmail.com

🙏 Acknowledgments
University Project Supervisor
Sir Uzair with thanks

Data Science & AI Program

Python Community

📚 References
WiFi-based occupancy detection systems

Bluetooth proximity sensing techniques

Real-time data processing methods

Data visualization best practices

⭐ Star this repository if you find it useful!

Last Updated: June 2026

