#!/usr/bin/env python3
"""
Auto-discovery tool for LMS courses.
This script discovers new courses on the LMS and adds them to the database.
"""

import requests
import asyncio
from playwright.async_api import async_playwright
import os
import sys
from dotenv import load_dotenv
import re

load_dotenv()

def create_module(unit_code, module_name, course_id):
    """Create a new module in the database"""
    module_data = {
        'uc_id': 1,  # Default coordinator - can be updated later
        'unit_code': unit_code,
        'module_name': module_name,
        'teaching_period': 'TMA',
        'semester': '2025',
        'module_description': f'Auto-discovered course from LMS (Course ID: {course_id})'
    }
    
    try:
        res = requests.post('http://127.0.0.1:8000/modules/', json=module_data)
        if res.status_code == 200:
            created = res.json()
            print(f"✅ Created Module {created['module_id']}: {created['unit_code']} - {created['module_name']}")
            return created['module_id']
        else:
            print(f"❌ Error creating module: {res.status_code} - {res.text}")
            return None
    except Exception as e:
        print(f"❌ Error creating module: {e}")
        return None

async def discover_courses():
    """Discover available courses on the LMS"""
    print("🔍 Starting course discovery...")
    
    discovered_courses = []
    
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # Login to LMS
            print("🔐 Logging into LMS...")
            await page.goto("http://10.51.33.25/moodle/login/index.php")
            
            # Fill login form
            await page.fill('input[name="username"]', os.getenv('MOODLE_USERNAME'))
            await page.fill('input[name="password"]', os.getenv('MOODLE_PASSWORD'))
            await page.click('button[type="submit"]')
            await page.wait_for_load_state('networkidle')
            
            # Try to find course discovery page or iterate through possible course IDs
            print("🔍 Discovering courses...")
            
            # Method 1: Try to find course list/catalog page
            try:
                await page.goto("http://10.51.33.25/moodle/course/")
                await page.wait_for_load_state('networkidle')
                
                # Look for course links
                course_links = await page.query_selector_all('a[href*="course/view.php?id="]')
                for link in course_links:
                    href = await link.get_attribute('href')
                    if href:
                        # Extract course ID
                        match = re.search(r'id=(\d+)', href)
                        if match:
                            course_id = int(match.group(1))
                            # Get course title
                            title = await link.text_content()
                            if title and title.strip():
                                discovered_courses.append({
                                    'course_id': course_id,
                                    'title': title.strip()
                                })
                                
            except Exception as e:
                print(f"⚠️ Course catalog method failed: {e}")
            
            # Method 2: Brute force check course IDs 1-20 (common range)
            if not discovered_courses:
                print("🔍 Trying brute force discovery...")
                
                for course_id in range(1, 21):
                    try:
                        course_url = f"http://10.51.33.25/moodle/course/view.php?id={course_id}"
                        response = await page.goto(course_url)
                        
                        if response.status == 200:
                            await page.wait_for_load_state('networkidle', timeout=5000)
                            
                            # Check if it's a valid course page (not error/login)
                            title_element = await page.query_selector('h1, .page-header-headings h1')
                            if title_element:
                                title = await title_element.text_content()
                                if title and 'error' not in title.lower() and 'login' not in title.lower():
                                    discovered_courses.append({
                                        'course_id': course_id,
                                        'title': title.strip()
                                    })
                                    print(f"   Found Course {course_id}: {title.strip()}")
                    
                    except Exception as e:
                        # Course probably doesn't exist, continue
                        continue
                        
        except Exception as e:
            print(f"❌ Error during discovery: {e}")
        
        finally:
            await browser.close()
    
    return discovered_courses

def extract_unit_code(title):
    """Extract unit code from course title"""
    # Look for patterns like "BSC203", "ICT280", etc.
    match = re.search(r'([A-Z]{2,4}\d{3})', title)
    if match:
        return match.group(1)
    
    # Fallback: use first word if it looks like a code
    words = title.split()
    if words and len(words[0]) <= 10 and any(c.isdigit() for c in words[0]):
        return words[0]
    
    return None

def get_existing_modules():
    """Get existing modules from database"""
    try:
        res = requests.get('http://127.0.0.1:8000/modules/')
        if res.status_code == 200:
            return res.json()
        return []
    except:
        return []

async def main():
    print("🚀 LMS Course Auto-Discovery Tool")
    print("=" * 50)
    
    # Discover courses
    discovered = await discover_courses()
    
    if not discovered:
        print("❌ No courses discovered")
        return
    
    print(f"\\n📊 Discovered {len(discovered)} courses:")
    for course in discovered:
        print(f"   Course {course['course_id']}: {course['title']}")
    
    # Get existing modules to avoid duplicates
    existing_modules = get_existing_modules()
    existing_course_ids = set()
    
    for module in existing_modules:
        # Calculate course_id from module_id (course_id = module_id + 1)
        course_id = module['module_id'] + 1
        existing_course_ids.add(course_id)
    
    print(f"\\n📋 Existing courses in database: {existing_course_ids}")
    
    # Create new modules for discovered courses
    new_modules = []
    for course in discovered:
        course_id = course['course_id']
        
        if course_id in existing_course_ids:
            print(f"⏭️ Course {course_id} already exists in database")
            continue
        
        # Extract unit code and prepare module data
        title = course['title']
        unit_code = extract_unit_code(title)
        
        if not unit_code:
            print(f"⚠️ Could not extract unit code from: {title}")
            continue
        
        print(f"➕ Creating new module for Course {course_id}: {unit_code}")
        
        # Calculate module_id (module_id = course_id - 1)
        # But we let the database auto-assign the module_id
        module_id = create_module(unit_code, title, course_id)
        
        if module_id:
            new_modules.append({
                'module_id': module_id,
                'course_id': course_id,
                'unit_code': unit_code,
                'title': title
            })
    
    print(f"\\n🎯 Summary:")
    print(f"   Discovered: {len(discovered)} courses")
    print(f"   New modules created: {len(new_modules)}")
    
    if new_modules:
        print(f"\\n✅ New modules:")
        for module in new_modules:
            print(f"   Module {module['module_id']}: {module['unit_code']} (Course {module['course_id']})")
    
    print(f"\\n💡 Run the scraper to collect data from new courses!")

if __name__ == "__main__":
    asyncio.run(main())
