# -*- coding: utf-8 -*-
"""
Created on Thu May 14 22:39:41 2026

@author: Tech
"""

import pandas as pendo
import os

# ==================== FILE PATHS ====================
PATIENTS_FILE = "patients.csv"
VITALS_FILE = "vitals.csv"

# ==================== LOAD EXISTING DATA ====================
def load_data():
#Load patients and vitals from CSV files if they exist
    if os.path.exists(PATIENTS_FILE):
        patients_df = pendo.read_csv(PATIENTS_FILE)
        patients = patients_df.to_dict('records')
    else:
        patients = []
    
    if os.path.exists(VITALS_FILE):
        vitals_df = pendo.read_csv(VITALS_FILE)
        vitals = vitals_df.to_dict('records')
    else:
        vitals = []
    
    return patients, vitals

# get current paths
print("Current path:", os.getcwd())

#I think we don't need to define the path for files, 
#The current path will be, from where the program will execute
# as printed in last line
# the Run path and current path is the same


# ==================== SAVE DATA ====================
def save_data(patients, vitals):
#Save patients and vitals to CSV files
    pendo.DataFrame(patients).to_csv(PATIENTS_FILE, index=False)
    pendo.DataFrame(vitals).to_csv(VITALS_FILE, index=False)
    print("\n✅ Data saved successfully!")

load_data()
patients = ["p00001-2026","Masood"]
vitals = ["O+","120bp"]
save_data(patients,vitals)


# so the next problem is, getting dictionary turn into table back again 
# when user select saving as an option... 