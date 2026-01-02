#!/usr/bin/env python3
"""
Script to update module mappings in the database to match actual course names.
This helps maintain consistency between database records and actual scraped courses.
"""

import requests
import sys

def get_modules():
    """Get current modules from the database"""
    try:
        res = requests.get('http://127.0.0.1:8000/modules/')
        if res.status_code == 200:
            return res.json()
        else:
            print(f"❌ Error fetching modules: {res.status_code} - {res.text}")
            return []
    except Exception as e:
        print(f"❌ Error connecting to API: {e}")
        return []

def update_module(module_id, unit_code, module_name, teaching_period='TMA', semester='2025', description=''):
    """Update a module's information"""
    update_data = {
        'uc_id': 1,  # Default coordinator ID
        'unit_code': unit_code,
        'module_name': module_name,
        'teaching_period': teaching_period,
        'semester': semester,
        'module_description': description
    }
    
    try:
        res = requests.put(f'http://127.0.0.1:8000/modules/{module_id}', json=update_data)
        if res.status_code == 200:
            updated = res.json()
            print(f"✅ Updated Module {module_id}: {updated['unit_code']} - {updated['module_name']}")
            return True
        else:
            print(f"❌ Error updating Module {module_id}: {res.status_code} - {res.text}")
            return False
    except Exception as e:
        print(f"❌ Error updating Module {module_id}: {e}")
        return False

def main():
    print("🔧 Module Mapping Update Tool")
    print("=" * 50)
    
    # Get current modules
    modules = get_modules()
    if not modules:
        print("❌ No modules found or error connecting to database")
        sys.exit(1)
    
    print("📊 Current modules:")
    for module in modules:
        print(f"   Module {module['module_id']}: {module['unit_code']} - {module['module_name']}")
    
    print("\n🔄 Applying standard course mappings...")
    
    # Standard mappings based on course IDs
    mappings = {
        1: {
            'unit_code': 'BSC203',
            'module_name': 'BSC203 Introduction to ICT Research Methods',
            'teaching_period': 'TJA',
            'description': 'Introduction to ICT Research Methods course (Course ID: 2)'
        },
        2: {
            'unit_code': 'ICT280',
            'module_name': 'ICT280 Information Security Policy and Governance', 
            'teaching_period': 'TMA',
            'description': 'Information Security Policy and Governance course (Course ID: 3)'
        }
    }
    
    success_count = 0
    for module_id, mapping in mappings.items():
        if update_module(
            module_id, 
            mapping['unit_code'], 
            mapping['module_name'],
            mapping['teaching_period'],
            '2025',
            mapping['description']
        ):
            success_count += 1
    
    print(f"\n🎯 Summary: Updated {success_count}/{len(mappings)} modules successfully")
    
    # Verify updates
    print("\n📊 Updated modules:")
    updated_modules = get_modules()
    for module in updated_modules:
        print(f"   Module {module['module_id']}: {module['unit_code']} - {module['module_name']}")

if __name__ == "__main__":
    main()
