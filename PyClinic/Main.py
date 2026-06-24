# -*- coding: utf-8 -*-
"""
Created on Thu May 14 22:39:41 2026

@author: M. Masood Saleem
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

# load_data()
# patients = ["p00001-2026","Masood"]
# vitals = ["O+","120bp"]
# save_data(patients,vitals)


# so the next problem is, getting dictionary turn into table back again 
# when user select saving as an option... 

# ==================== 1. ADD PATIENT (Auto ID) ====================
def add_patient(patients):
    """Add a new patient with auto-generated ID (P00001-2026 format)"""
    print("\n" + "="*50)
    print("ADD NEW PATIENT")
    print("="*50)
    
    # Auto-generate ID
    current_year = datetime.now().strftime("%Y")
    
    if patients:
        existing_nums = []
        for p in patients:
            if '-' in p['id']:
                num_part = p['id'].split('-')[0][1:]
                try:
                    existing_nums.append(int(num_part))
                except:
                    pass
        if existing_nums:
            next_num = max(existing_nums) + 1
        else:
            next_num = 1
    else:
        next_num = 1
    
    patient_id = f"P{next_num:05d}-{current_year}"
    print(f"Auto-generated Patient ID: {patient_id}")
    
    name = input("Enter Patient Name: ")
    blood_type = input("Enter Blood Type (A+/A-/B+/B-/O+/O-/AB+/AB-): ")
    phone = input("Enter Phone Number: ")
    
    patient = {
        'id': patient_id,
        'name': name,
        'blood_type': blood_type,
        'phone': phone,
        'created_date': datetime.now().strftime("%Y-%m-%d")
    }
    
    patients.append(patient)
    print(f"\n✅ Patient {name} (ID: {patient_id}) added successfully!")
    return patients

# ==================== 2. VIEW ALL PATIENTS ====================
def view_patients(patients):
    """Display all patients in a formatted table"""
    print("\n" + "="*60)
    print("ALL PATIENTS")
    print("="*60)
    
    if not patients:
        print("No patients found. Please add patients first.")
        return
    
    print(f"{'ID':<15} {'Name':<20} {'Blood Type':<12} {'Phone':<15}")
    print("-"*62)
    
    for p in patients:
        print(f"{p['id']:<15} {p['name']:<20} {p['blood_type']:<12} {p['phone']:<15}")
    
    print("-"*62)
    print(f"Total Patients: {len(patients)}")














# ==================== MAIN MENU ====================
def main():
    """Main program loop"""
    print("\n" + "="*50)
    print("HEALTH PATIENT MANAGEMENT SYSTEM ")
    print("="*50)
    print("Masood Saleem - Python Real-World Assignment")
    print("NED Academy - PGD in Data Science with AI")
    print("="*50)
    
    patients, vitals = load_data()
    print(f"\n Loaded: {len(patients)} patients, {len(vitals)} vital records")
    
    while True:
        print("\n" + "-"*40)
        print("MAIN MENU")
        print("-"*40)
        print("1. Add New Patient")
        print("2. View All Patients")
        print("3. Search Patient (by ID/Name)")
        print("4. Modify Existing Patient")
        print("5. Delete Patient")
        print("6. Add Patient Vitals")
        print("7. View Summary Statistics")
        print("8. Show Chart & Visualization")
        print("9. Export to Excel")
        print("10. Save & Exit")
        print("-"*40)
        
        choice = input("Enter your choice (1-10): ").strip() #remove spaces
        
        if choice == '1':
            patients = add_patient(patients)
        elif choice == '2':
            view_patients(patients)
        elif choice == '3':
            search_patient(patients, vitals)
        elif choice == '4':
            patients = modify_patient(patients)
        elif choice == '5':
            patients, vitals = delete_patient(patients, vitals)
        elif choice == '6':
            vitals = add_vitals(patients, vitals)
        elif choice == '7':
            view_summary(patients, vitals)
        elif choice == '8':
            show_chart(patients, vitals)
        elif choice == '9':
            export_to_excel(patients, vitals)
        elif choice == '10':
            save_data(patients, vitals) #def done
            print("\n Thank you for using Health Patient System!")
            print(" Goodbye, Masood!")
            break
        else:
            print(" Invalid choice! Please enter 1-10.")

# ==================== RUN THE APP ====================
if __name__ == "__main__":
    main()