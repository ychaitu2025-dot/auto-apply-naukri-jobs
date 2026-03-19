import os
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import ElementClickInterceptedException
from dotenv import load_dotenv
import time
import re
import pyautogui
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import argparse

try:
    import pandas as pd
except ImportError:
    pass

# Try both absolute and relative imports for compatibility
try:
    from naukri_auto_apply.core.browser_detector import get_browser_path
    from naukri_auto_apply.core.naukri_login import login_to_naukri
except ImportError:
    try:
        from ..core.browser_detector import get_browser_path
        from ..core.naukri_login import login_to_naukri
    except ImportError:
        from core.browser_detector import get_browser_path
        from core.naukri_login import login_to_naukri


# Load environment variables
load_dotenv()

def get_web_driver(headless=False, retry_with_alternative=True):
    """
    Initializes a Selenium WebDriver with fallback options.
    If the primary browser (Brave) fails to load, it will try Chrome as a fallback.
    
    Parameters:
        headless (bool): Whether to use headless mode
        retry_with_alternative (bool): Whether to try alternative browsers if primary fails
        
    Returns:
        WebDriver: Initialized WebDriver instance
    """
    # Fix ChromeDriver permissions first
    try:
        # Import fix_chromedriver
        import sys
        import os
        
        # Add the parent directory to the path to find fix_chromedriver
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
            
        # Run fix_chromedriver
        from fix_chromedriver import fix_chromedriver_permissions
        fix_chromedriver_permissions()
    except Exception as e:
        print(f"Warning: Could not fix ChromeDriver permissions: {e}")


    import platform  # Add this import for system detection
    
    # Get browser path from .env or detect it
    web_browser_path = get_browser_path()
    
    if not web_browser_path:
        raise Exception("Browser path not found in .env file. Please set WEB_BROWSER_PATH.")

    tried_browsers = []
    
    # Try the primary browser first
    try:
        options = Options()
        options.binary_location = web_browser_path
        
        # Add headless mode options if requested
        if headless:
            options.add_argument("--headless")
            
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-web-security")
        options.add_argument("--disable-features=EnableEphemeralFlashPermission")
        options.add_argument("--no-sandbox")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-notifications")
        
        # Clear browser cache and cookies
        options.add_argument("--disable-application-cache")
        options.add_argument("--incognito")

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Test navigation to a simple page to verify browser is working
        driver.get("https://www.google.com")
        driver.find_element(By.TAG_NAME, "body")  # Should work if page loaded
        
        print(f"Successfully initialized browser: {os.path.basename(web_browser_path)}")
        return driver
        
    except Exception as e:
        tried_browsers.append(os.path.basename(web_browser_path))
        print(f"Error initializing primary browser ({os.path.basename(web_browser_path)}): {e}")
        
        if not retry_with_alternative:
            raise Exception(f"Failed to initialize browser and retry is disabled.")
    
    # If we get here, the primary browser failed - let's try alternatives
    system = platform.system()
    alternative_paths = []
    
    if system == "Darwin":  # macOS
        alternative_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Firefox.app/Contents/MacOS/firefox",
            "/Applications/Safari.app/Contents/MacOS/Safari"
        ]
    elif system == "Windows":
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
        alternative_paths = [
            f"{program_files}\\Google\\Chrome\\Application\\chrome.exe",
            f"{program_files_x86}\\Google\\Chrome\\Application\\chrome.exe",
            f"{program_files}\\Mozilla Firefox\\firefox.exe",
            f"{program_files_x86}\\Mozilla Firefox\\firefox.exe"
        ]
    else:  # Linux
        alternative_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/firefox"
        ]
    
    # Try each alternative browser
    for alt_path in alternative_paths:
        if alt_path not in tried_browsers and os.path.exists(alt_path):
            try:
                options = Options()
                options.binary_location = alt_path
                
                if headless:
                    options.add_argument("--headless")
                    
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_argument("--incognito")  # Use incognito to avoid cache issues
                
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                # Test navigation
                driver.get("https://www.google.com")
                driver.find_element(By.TAG_NAME, "body")
                
                print(f"Successfully initialized alternative browser: {os.path.basename(alt_path)}")
                
                # Update the .env file with working browser
                from dotenv import set_key, find_dotenv
                dotenv_path = find_dotenv()
                if dotenv_path:
                    set_key(dotenv_path, "WEB_BROWSER_PATH", alt_path)
                    print(f"Updated WEB_BROWSER_PATH in .env file to: {alt_path}")
                
                return driver
                
            except Exception as e:
                tried_browsers.append(os.path.basename(alt_path))
                print(f"Error initializing alternative browser ({os.path.basename(alt_path)}): {e}")
    
    # If we get here, all browsers failed
    raise Exception(f"Failed to initialize any browser. Tried: {', '.join(tried_browsers)}")



def apply_to_job_url(driver, job_url):
    """
    Applies to a job without opening a new tab, preventing focus stealing.
    Instead navigates to job URL in the same tab and returns to original URL when done.
    """
    # Store current URL to return to later
    original_url = driver.current_url
    
    # Navigate to job URL in the same tab
    driver.get(job_url)
    
    # Give the page time to load
    wait = WebDriverWait(driver, 15)
    applied = False
    
    # move pointer to prevent sleeping
    pyautogui.moveRel(1, 1, duration=0.1)
    pyautogui.moveRel(-1, -1, duration=0.1)

    try:
        # Wait 3 seconds for dynamic content
        time.sleep(3)
        
        # Look for buttons containing apply text using specific Naukri classes or text nodes
        # Naukri usually has buttons with IDs/classes like 'apply-button', 'pdp-apply-btn', etc.
        # We will fallback to a generic text match if specific classes aren't found.
        target_button = None
        already_applied = False
        company_site = False
        
        # 1. First, check status texts via xpath (already applied or company site)
        try:
            status_elements = driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'already applied') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'company site')]")
            for el in status_elements:
                if el.is_displayed():
                    text = el.text.strip().lower()
                    if 'already applied' in text:
                        already_applied = True
                        break
                    elif 'company site' in text:
                        company_site = True
                        break
        except Exception:
            pass
            
        # 2. If not already applied/company site, find the exact Apply button
        if not already_applied and not company_site:
            try:
                # Priority 1: Use the confirmed Naukri Apply button ID
                try:
                    btn = driver.find_element(By.ID, 'apply-button')
                    if btn.is_displayed():
                        target_button = btn
                except Exception:
                    pass
                
                # Priority 2: Fallback to class-based selectors
                if not target_button:
                    xpath_query = (
                        "//button[contains(@class, 'apply-button') or contains(@class, 'apply-message')] | "
                        "//button[translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='apply'] | "
                        "//button[translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='apply now'] | "
                        "//button[translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='easy apply']"
                    )
                    potential_buttons = driver.find_elements(By.XPATH, xpath_query)
                    
                    for btn in potential_buttons:
                        if btn.is_displayed():
                            text = driver.execute_script("return arguments[0].innerText", btn).strip().lower()
                            if text in ['apply', 'apply now', 'easy apply']:
                                target_button = btn
                                break
            except Exception as e:
                print(f"Error finding apply button: {e}")


        if already_applied:
            print(f"Skipping this Job as it is already applied: {job_url}")
            applied = True
            
        elif company_site:
            print(f"Skipping this Job as it requires applying on company site: {job_url}")
            applied = False
            
        elif target_button:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", target_button)
                time.sleep(1)
                
                # Try clicking via JS for reliability
                driver.execute_script("arguments[0].click();", target_button)
                print("Clicked Apply button. Waiting for confirmation...")
                
                # Wait up to 30 seconds for application confirmation
                success = False
                questionnaire_answered = set()  # Track which questions we already answered
                
                for attempt in range(30):
                    time.sleep(1)
                    
                    # ---- Check 1: Did the URL change to the saveApply endpoint? ----
                    current_url = driver.current_url
                    if 'saveApply' in current_url or 'myapply' in current_url:
                        print("Application confirmed via saveApply URL!")
                        success = True
                        break
                    
                    # ---- Check 2: Is the page title/tab 'Apply Confirmation'? ----
                    try:
                        page_title = driver.title.lower()
                        if 'apply confirmation' in page_title or 'application submitted' in page_title:
                            print("Application confirmed via page title!")
                            success = True
                            break
                    except Exception:
                        pass
                    
                    # ---- Check 3: Did the button text change to 'Applied'? ----
                    try:
                        btn_txt = driver.execute_script("return arguments[0].innerText", target_button)
                        if btn_txt and btn_txt.strip().lower() in ['applied', 'application submitted']:
                            print("Application confirmed: button text changed to Applied")
                            success = True
                            break
                    except Exception:
                        pass
                    
                    # ---- Check 4: Green 'Applied to' banner OR error banner in body ----
                    # CONFIRMED from live page screenshots:
                    #   SUCCESS: "Applied to [Job Title]" (green banner with checkmark)
                    #   ERROR:   "Oops! Your application was not accepted due to incomplete information."
                    try:
                        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
                        if "applied to" in page_text or "successfully applied" in page_text or "thank you for applying" in page_text:
                            print("Application confirmed via 'Applied to' banner!")
                            success = True
                            break
                        # Detect error state early — no point waiting further
                        if "not accepted due to incomplete" in page_text or "mandatory questions when reapplying" in page_text:
                            print(f"Application rejected — incomplete profile: {job_url}")
                            success = False
                            break
                    except Exception:
                        pass

                    
                    # ---- Action A: Handle the Naukri chatbot popup (resume upload prompt) ----
                    # When Naukri shows "Please upload your resume. Upload Resume | I'll do it later"
                    try:
                        dismiss_xpaths = [
                            "//button[contains(text(), \"I'll do it later\")]",
                            "//span[contains(text(), \"I'll do it later\")]",
                            "//div[contains(text(), \"I'll do it later\")]",
                            "//*[contains(text(), \"I'll do it later\")]",
                            "//*[contains(text(), 'do it later')]",
                            "//*[contains(text(), 'skip')]",
                        ]
                        for xpath in dismiss_xpaths:
                            dismiss_btns = driver.find_elements(By.XPATH, xpath)
                            for d_btn in dismiss_btns:
                                if d_btn.is_displayed():
                                    driver.execute_script("arguments[0].click();", d_btn)
                                    print("Dismissed 'Upload Resume' popup (clicked I'll do it later)")
                                    time.sleep(1)
                                    break
                            else:
                                continue
                            break
                    except Exception:
                        pass
                    
                    # ---- Action B: Handle questionnaire Yes/No prompts ----
                    # Only answer each unique question once to avoid infinite loop
                    try:
                        radio_labels = driver.find_elements(
                            By.XPATH, 
                            "//label[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'no')]"
                        )
                        for label in radio_labels:
                            if label.is_displayed():
                                label_text = label.text.strip()
                                parent_text = ""
                                try:
                                    parent_text = label.find_element(By.XPATH, "./..").text.strip()
                                except Exception:
                                    pass
                                question_key = parent_text or label_text
                                if question_key not in questionnaire_answered:
                                    try:
                                        driver.execute_script("arguments[0].click();", label)
                                        time.sleep(0.5)
                                        questionnaire_answered.add(question_key)
                                        print(f"Answered 'No' to question: {question_key[:50]}")
                                    except Exception:
                                        pass
                    except Exception:
                        pass
                    
                    # ---- Action C: Click Submit/Save if visible ----
                    try:
                        for btn_text_match in ['submit', 'send application', 'update and apply', 'save and apply']:
                            match_btns = driver.find_elements(
                                By.XPATH,
                                f"//button[translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='{btn_text_match}']"
                            )
                            for m_btn in match_btns:
                                if m_btn.is_displayed():
                                    driver.execute_script("arguments[0].click();", m_btn)
                                    print(f"Clicked '{btn_text_match}' button")
                                    time.sleep(2)
                                    break
                    except Exception:
                        pass
                        
                if success:
                    print(f"✅ Application confirmed for: {job_url}")
                    applied = True
                else:
                    print(f"⚠ Could not confirm application submission: {job_url}")
                    applied = False
                    
            except Exception as e:
                print(f"Failed to click Apply button: {e}")
                applied = False
        else:
            print(f"No valid Apply button found or you are logged out: {job_url}")
            applied = False
            
    except Exception as e:
        print(f"Error in application process: {e}")
        applied = False
        
    # Always return to the original URL
    driver.get(original_url)
    return applied


def fetch_jobs_with_requests(driver, search_keyword, include_keywords=None, exclude_keywords=None, location="", experience="0 years (Fresher)", workplace_type="Any"):
    """
    Fetches jobs using Selenium since Naukri relies heavily on JavaScript.
    Handles Naukri's anti-bot measures by simulating human behavior and using undetected-chromedriver concepts.
    Now supports location, experience, and workplace type filters.
    """
    print(f"\nSearching Naukri for -> {search_keyword}")
    if location:
        print(f"Location: {location}")
    if experience:
        print(f"Experience: {experience}")
    if workplace_type != "Any":
        print(f"Workplace: {workplace_type}")
        
    formatted_keyword = search_keyword.replace(' ', '-')
    
    # Base URL parsing
    if location:
        formatted_location = location.lower().replace(' ', '-')
        base_url = f"https://www.naukri.com/{formatted_keyword}-jobs-in-{formatted_location}"
    else:
        base_url = f"https://www.naukri.com/{formatted_keyword}-jobs"
        
    # Build query parameters
    params = []
    
    # 1. Experience Mapping
    # Format: "X years" -> extract X
    if experience and "years" in experience.lower():
        try:
            # Handle "8+ years" or "0 years (Fresher)"
            exp_val = experience.split()[0].replace('+', '')
            params.append(f"experience={exp_val}")
        except:
            pass
            
    # 2. Workplace Type Mapping
    # VERIFIED from live page testing:
    #   wfhType=0 -> Work from office
    #   wfhType=1 -> Temp. WFH due to covid (almost no results)
    #   wfhType=2 -> Remote (full remote / work from home)
    #   wfhType=3 -> Hybrid
    if workplace_type == "Remote":
        params.append("wfhType=2")
    elif workplace_type == "Hybrid":
        params.append("wfhType=3")
    elif workplace_type == "In Office":
        params.append("wfhType=0")

        
    # Append params to base URL if they exist
    if params:
        base_url += "?" + "&".join(params)
    
    print(f"Constructed URL: {base_url}")
    
    included_jobs = []
    excluded_jobs = []
    total_jobs_found = 0
    
    # Create WebDriverWait objects with different timeout values
    short_wait = WebDriverWait(driver, 20)
    medium_wait = WebDriverWait(driver, 60)  # Increased timeout for slow loading
    
    try:
        # First load the initial page
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"Loading search results for query: '{search_keyword}'...")
                driver.get(base_url)
                short_wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"Error loading initial page. Retry {attempt+1}/{max_retries}...")
                else:
                    print(f"Failed to load initial page after {max_retries} attempts.")
                    raise e
        
        # Move mouse to prevent system sleeping
        pyautogui.moveRel(1, 1, duration=0.1)
        pyautogui.moveRel(-1, -1, duration=0.1)
        
        # ============================================================
        # WAIT FOR PAGE TO FULLY LOAD (filters applied via URL params already)
        # ============================================================
        # The filter params (wfhType, experience) are already in the URL.
        # We just need to wait for the page to fully render before extracting jobs.
        try:
            print("Waiting for job results to load (shimmer to disappear)...")
            # Wait until at least one real job card is visible (not shimmer)
            medium_wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.srp-jobtuple-wrapper, article.jobTuple"))
            )
            time.sleep(2)  # Extra buffer for dynamic content
            print("Job results loaded successfully.")
        except Exception as e:
            print(f"Wait for job cards timed out: {e}. Proceeding anyway...")
        # ============================================================
        

        # Get total jobs count
        total_pages = 1
        try:
            print("Looking for job count element...")
            body_text = driver.find_element(By.TAG_NAME, "body").text
            
            total_jobs_match = re.search(r'of\s+([0-9,]+)', body_text)
            
            if total_jobs_match:
                total_jobs = int(total_jobs_match.group(1).replace(',', ''))
                print(f"Total jobs for query '{search_keyword}': {total_jobs}")
                
                # 20 jobs per page
                jobs_per_page = 20
                total_pages = min(11, (total_jobs + jobs_per_page - 1) // jobs_per_page)
                print(f"Will process {total_pages} pages ({jobs_per_page} jobs per page)")
            else:
                print(f"Could not extract parseable job count")
                total_pages = 3  # Default to 3 pages
            
        except Exception as e:
            print(f"Could not find total job count, defaulting to 3 pages: {str(e)}")
            total_pages = 3
        
        # Process each page
        for page in range(1, total_pages + 1):
            if page == 1:
                url = base_url
            else:
                # Handle pagination logic with existing params
                if "?" in base_url:
                    url = base_url.replace("?", f"-{page}?", 1)
                else:
                    url = f"{base_url}-{page}"
                
            print(f"\nFetching page {page}...")
            print(f"URL: {url}")
            
            try:
                driver.get(url)
                short_wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            except Exception as e:
                print(f"Error loading page {page}: {e}")
                continue
            
            # Wait for job cards to appear with a more specific selector based on example
            try:
                print("Waiting for job cards to load...")
                
                # NEW APPROACH: Wait specifically for job cards using data attributes
                medium_wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.srp-jobtuple-wrapper, div.jobTuple"))
                )
                
                # Add a small delay to ensure dynamic content is fully rendered
                time.sleep(2)
                
                # Get all job cards using the data-id and data-job-guid attributes
                job_cards = driver.find_elements(By.CSS_SELECTOR, "div.srp-jobtuple-wrapper, div.jobTuple")
                
                if not job_cards:
                    print(f"No job cards found on page {page}")
                    continue
                    
                print(f"Found {len(job_cards)} jobs on page {page}")
                
                # Process each job card
                for card_index, card in enumerate(job_cards):
                    try:
                        # Extract job title
                        try:
                            job_title_element = card.find_element(By.CSS_SELECTOR, "a.title")
                            job_title = job_title_element.text.strip()
                            job_url = job_title_element.get_attribute('href')
                        except:
                            job_title = "Unknown"
                            job_url = ""
                        
                        if not job_url:
                            print(f"Missing job_url on card {card_index}")
                            continue

                        # Extract company name
                        try:
                            company_element = card.find_element(By.CSS_SELECTOR, "a.comp-name")
                            company_name = company_element.text.strip()
                        except:
                            company_name = "Unknown"
                        
                        # Extract location
                        try:
                            location_elements = card.find_elements(By.CSS_SELECTOR, "span.locWdth, span.loc")
                            job_location = location_elements[0].text.strip() if location_elements else "Unknown"
                        except:
                            job_location = "Unknown"
                        
                        job_employment_type = "Unknown"
                        job_posted_date = "Recently"
                        
                        # Create job entry
                        job_entry = {
                            "Job Title": job_title,
                            "Job URL": job_url,
                            "Company": company_name,
                            "Location": job_location,
                            "Employment Type": job_employment_type,
                            "Posted Date": job_posted_date,
                            "Applied": False
                        }
                        
                        # Apply filtering
                        include_job = True
                        exclusion_reason = ""
                        job_title_lower = job_title.lower()
                        
                        # Check exclude keywords
                        if exclude_keywords and any(keyword.lower() in job_title_lower for keyword in exclude_keywords):
                            matching_keywords = [kw for kw in exclude_keywords if kw.lower() in job_title_lower]
                            exclusion_reason = f"Contains excluded keywords: {', '.join(matching_keywords)}"
                            include_job = False
                        
                        # Check include keywords
                        if include_keywords and not any(keyword.lower() in job_title_lower for keyword in include_keywords):
                            exclusion_reason = f"Missing required keywords: {', '.join(include_keywords)}"
                            include_job = False
                        
                        if include_job:
                            included_jobs.append(job_entry)
                        else:
                            job_entry["Exclusion Reason"] = exclusion_reason
                            excluded_jobs.append(job_entry)
                    
                    except Exception as e:
                        print(f"Error processing job card {card_index} on page {page}: {str(e)}")
                        continue
                
                total_jobs_found += len(job_cards)
                
            except Exception as e:
                print(f"Error processing job cards on page {page}: {str(e)}")
                
    except Exception as e:
        print(f"Error during job fetching: {str(e)}")
    
    print(f"Total jobs processed: {total_jobs_found}")
    print(f"Jobs included after filtering: {len(included_jobs)}")
    print(f"Jobs excluded after filtering: {len(excluded_jobs)}")
    
    return included_jobs, excluded_jobs


            

def save_to_excel(job_data, filename="job_application_report.xlsx"):
    """
    Saves job data to an Excel file.
    """
    try:
        df = pd.DataFrame(job_data["jobs"])
        df.to_excel(filename, index=False)
        print(f"Job application report saved to {filename}")
    except Exception as e:
        print(f"Error saving to Excel: {e}")

def main():
    # Record the start time of the entire script
    script_start_time = time.time()
    
    # Disable PyAutoGUI failsafe to prevent accidental triggering
    pyautogui.FAILSAFE = False
    
    driver = get_web_driver()  # Use browser
    
    # Define file names for fresh start
    applied_jobs_file = "applied_jobs.xlsx"
    not_applied_jobs_file = "not_applied_jobs.xlsx"
    job_report_file = "job_application_report.xlsx"
    excluded_jobs_file = "excluded_jobs.xlsx"
 
    # Delete existing files before login to start fresh (excluding applied_jobs.xlsx)
    for file in [not_applied_jobs_file, job_report_file, excluded_jobs_file]:
        if os.path.exists(file):
            os.remove(file)
            
    # Ensure applied_jobs.xlsx exists before writing
    if not os.path.exists(applied_jobs_file):
        df_empty = pd.DataFrame(columns=["Job Title", "Job URL", "Company", "Location", "Employment Type", "Posted Date", "Applied"])
        df_empty.to_excel(applied_jobs_file, index=False)

    job_data = {
        "Total Jobs Posted Today": 0,
        "jobs": []
    }

    try:
        # Record login start time
        login_start_time = time.time()
        
        if login_to_naukri(driver):
            login_time = time.time() - login_start_time
            print(f"Login successful in {login_time:.2f} seconds. Starting job search...")

            # Move mouse to prevent system sleeping
            pyautogui.moveRel(1, 1, duration=0.1)
            pyautogui.moveRel(-1, -1, duration=0.1)

            # Use existing driver to fetch jobs
            collected_jobs = {}  # Dictionary to hold unique jobs by URL
            excluded_jobs = []   # List to hold excluded jobs
            fetch_start_time = time.time()
            
            for query in NAUKRI_SEARCH_QUERIES:
                # Pass the existing driver to fetch_jobs_with_requests
                included_jobs, query_excluded_jobs = fetch_jobs_with_requests(driver, query, INCLUDE_KEYWORDS, EXCLUDE_KEYWORDS)
                
                # Add each job to the collected jobs dictionary
                for job in included_jobs:
                    if job["Job URL"] not in collected_jobs:
                        collected_jobs[job["Job URL"]] = job
                
                # Add to excluded jobs list
                excluded_jobs.extend(query_excluded_jobs)
                
                print(f"Query '{query}' returned {len(included_jobs)} jobs")
                
                # Mouse movement between queries to prevent sleep
                pyautogui.moveRel(1, 1, duration=0.1)
                pyautogui.moveRel(-1, -1, duration=0.1)
                
            fetch_time = time.time() - fetch_start_time
            print(f"Finished fetching jobs in {fetch_time:.2f} seconds")

            # Save excluded jobs to Excel
            if excluded_jobs:
                df_excluded = pd.DataFrame(excluded_jobs)
                df_excluded.to_excel(excluded_jobs_file, index=False)
                print(f"Saved {len(excluded_jobs)} excluded jobs to {excluded_jobs_file}")

            # Merge all job details into job_data
            job_data["jobs"] = list(collected_jobs.values())
            print(f"==========> Total unique jobs collected from all queries: {len(job_data['jobs'])}")
            
            # Rest of your code stays the same...
            # Check for already applied jobs
            if not os.path.exists(not_applied_jobs_file):
                df_empty = pd.DataFrame(columns=["Job Title", "Job URL", "Company", "Location", "Employment Type", "Posted Date", "Applied"])
                df_empty.to_excel(not_applied_jobs_file, index=False)
                
            existing_applied_jobs = set()
            existing_not_applied_jobs = set()

            if os.path.exists(applied_jobs_file):
                try:
                    df_applied = pd.read_excel(applied_jobs_file)
                    existing_applied_jobs = set(df_applied["Job URL"].dropna())
                except Exception as e:
                    print(f"Error loading existing applied jobs: {e}")

            if os.path.exists(not_applied_jobs_file):
                try:
                    df_not_applied = pd.read_excel(not_applied_jobs_file)
                    existing_not_applied_jobs = set(df_not_applied["Job URL"].dropna())
                except Exception as e:
                    print(f"Error loading not applied jobs: {e}")

            # Count already applied jobs
            already_applied_count = sum(1 for job in job_data["jobs"] if job["Job URL"] in existing_applied_jobs)
            print(f"==========> Skipping jobs that were already applied: {already_applied_count}")

            # Filter jobs before applying
            pending_jobs = [job for job in job_data["jobs"] if job["Job URL"] not in existing_applied_jobs]
            print(f"==========> Total jobs to apply for: {len(pending_jobs)}")
            
            # Calculate and display the estimated time
            print(f"==========> Estimated time to apply all {len(pending_jobs)} jobs: {len(pending_jobs)//8//60} hours {len(pending_jobs)//8%60} minutes")
            
            # Record application start time
            apply_start_time = time.time()
            successful_applications = 0
            failed_applications = 0
            
            # Process only pending jobs
            for job_index, job in enumerate(pending_jobs):
                # Move mouse every 3 jobs to prevent system sleeping
                if job_index % 3 == 0:
                    pyautogui.moveRel(1, 1, duration=0.1)
                    pyautogui.moveRel(-1, -1, duration=0.1)
                
                job_start_time = time.time()
                
                if not job["Applied"] and job["Job URL"] != "Unknown":
                    applied = apply_to_job_url(driver, job["Job URL"])
                    job["Applied"] = applied
                    
                    job_time = time.time() - job_start_time
                    
                    if applied:
                        successful_applications += 1
                        try:
                            df_existing = pd.read_excel(applied_jobs_file)
                        except Exception:
                            df_existing = pd.DataFrame(columns=["Job Title", "Job URL", "Company", "Location", "Employment Type", "Posted Date", "Applied"])
                        df_new = pd.DataFrame([job])
                        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                        df_combined.to_excel(applied_jobs_file, index=False)
                    else:
                        failed_applications += 1
                        try:
                            df_existing = pd.read_excel(not_applied_jobs_file)
                        except Exception:
                            df_existing = pd.DataFrame(columns=["Job Title", "Job URL", "Company", "Location", "Employment Type", "Posted Date", "Applied"])
                        df_new = pd.DataFrame([job])
                        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                        df_combined.to_excel(not_applied_jobs_file, index=False)
                    
                    # Print progress every 5 jobs
                    if (job_index + 1) % 5 == 0 or job_index == len(pending_jobs) - 1:
                        elapsed = time.time() - apply_start_time
                        progress = (job_index + 1) / len(pending_jobs) * 100
                        estimated_total = elapsed / (job_index + 1) * len(pending_jobs)
                        remaining = estimated_total - elapsed
                        
                        print(f"Progress: {job_index+1}/{len(pending_jobs)} jobs ({progress:.1f}%) | "
                              f"Last job: {job_time:.1f}s | "
                              f"Success rate: {successful_applications}/{job_index+1} | "
                              f"Est. remaining: {remaining/60:.1f} mins")

            apply_time = time.time() - apply_start_time
            applications_per_minute = (successful_applications + failed_applications) / (apply_time / 60) if apply_time > 0 else 0
            print(f"\n==========> Application phase completed in {apply_time:.2f} seconds")
            print(f"==========> Successfully applied: {successful_applications} jobs")
            print(f"==========> Failed applications: {failed_applications} jobs")
            print(f"==========> Average application rate: {applications_per_minute:.2f} jobs per minute")

            # Save final data to JSON
            with open("job_data.json", "w") as json_file:
                json.dump(job_data, json_file, indent=4)
            print("Job data saved to job_data.json")

            # Final save to Excel
            save_to_excel(job_data)

        else:
            print("Login failed. Exiting...")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        pass
        # Don't close the browser immediately for debugging
        # driver.quit()
        
    # Calculate and print total execution time
    total_time = time.time() - script_start_time
    hours, remainder = divmod(total_time, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    print("\n===== EXECUTION TIME SUMMARY =====")
    print(f"Total script execution time: {int(hours)}h {int(minutes)}m {seconds:.2f}s")
    if 'pending_jobs' in locals() and pending_jobs:
        print(f"Average time per job processed: {total_time/len(pending_jobs):.2f} seconds")
    print("==================================")



if __name__ == "__main__":
    # Search in naukri
    NAUKRI_SEARCH_QUERIES = [" "," "]  # You can update this list anytime

    # Optional: Define keywords for filtering job applications
    EXCLUDE_KEYWORDS = [" "," "]  # Add more if needed
    INCLUDE_KEYWORDS = [" "," "]  # Add more if needed

    start_time = datetime.datetime.now()
    main()
    end_time = datetime.datetime.now()
    print(f"Exact Execution time: {end_time - start_time}")