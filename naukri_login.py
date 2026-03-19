import os
import time
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv, set_key, find_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def update_naukri_credentials(username, password, update_env=True):
    """
    Updates the Naukri credentials in the .env file.
    
    Parameters:
        username (str): Naukri account email/username
        password (str): Naukri account password
        update_env (bool): Whether to update the .env file or not
        
    Returns:
        bool: True if credentials were updated successfully
    """
    if not username or not password:
        print("Invalid credentials provided. Both username and password are required.")
        return False
    
    try:
        if update_env:
            # Find or create .env file
            dotenv_path = find_dotenv()
            if not dotenv_path:
                dotenv_path = os.path.join(os.getcwd(), '.env')
                Path(dotenv_path).touch(exist_ok=True)
                print(f"Created new .env file at {dotenv_path}")
            
            # Load existing .env file
            load_dotenv(dotenv_path)
            
            # Update credentials in .env file
            set_key(dotenv_path, "NAUKRI_USERNAME", username)
            set_key(dotenv_path, "NAUKRI_PASSWORD", password)
            print("Naukri credentials updated in .env file.")
        
        # Set the environment variables for current session
        os.environ["NAUKRI_USERNAME"] = username
        os.environ["NAUKRI_PASSWORD"] = password
        
        return True
    except Exception as e:
        print(f"Error updating credentials: {e}")
        return False

def get_headless_driver():
    """
    Creates a headless WebDriver for credential validation
    
    Returns:
        webdriver: A headless Chrome/Brave WebDriver instance
    """
    try:
        # Import browser detector if available
        from browser_detector import get_browser_path
        web_browser_path = get_browser_path()
    except ImportError:
        # Fallback if browser_detector is not available
        web_browser_path = None
    
    options = Options()
    
    # Add headless options
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    
    # Set browser binary location if available
    if web_browser_path:
        options.binary_location = web_browser_path
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def validate_naukri_credentials(username, password, headless=False):
    """
    Validates Naukri credentials by attempting to log in using a headless browser.
    With enhanced waiting times for slow login processes.
    
    Parameters:
        username (str): Naukri account email/username
        password (str): Naukri account password
        headless (bool): Whether to use headless mode for validation
        
    Returns:
        bool: True if login was successful, False otherwise
    """
    print(f"Validating credentials for {username}...")
    
    # Create driver (headless or regular)
    if headless:
        driver = get_headless_driver()
    else:
        # Import from main file to get regular driver
        from browser_detector import get_browser_path
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        
        web_browser_path = get_browser_path()
        options = Options()
        options.binary_location = web_browser_path
        options.add_argument("--start-maximized")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        # Try login with provided credentials
        driver.get("https://www.naukri.com/nlogin/login")
        wait = WebDriverWait(driver, 20)
        long_wait = WebDriverWait(driver, 180) # 3 mins for OTP
        
        try:
            # Enter email/username
            email_field = wait.until(EC.presence_of_element_located((By.ID, "usernameField")))
            email_field.clear()
            email_field.send_keys(username)
            
            # Enter password
            password_field = wait.until(EC.presence_of_element_located((By.ID, "passwordField")))
            password_field.clear()
            password_field.send_keys(password)
            
            # Click login button
            login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']")))
            login_button.click()
            print("Credentials entered. Please complete OTP if prompted.")
        except Exception as e:
            print("Auto-fill failed, you may need to login manually:", str(e))
        
        # Add a pause
        print("Waiting for login to complete (this may take up to 3 minutes for OTP)...")
        time.sleep(5)
        
        # Check for successful login
        try:
            # Wait for mnjuser homepage
            long_wait.until(EC.url_contains("mnjuser"))
            print("Login successful! Reached mnjuser homepage.")
            return True
        except Exception:
            print("Login failed: Did not reach mnjuser homepage within timeout.")
            return False
            
    except Exception as e:
        print(f"Error validating credentials: {e}")
        return False
    finally:
        driver.quit()


def login_to_naukri(driver, credentials_from_params=None):
    """
    Logs into Naukri using credentials from the .env file or provided parameters.
    With enhanced waiting and retry logic for slow login processes.
    
    Parameters:
        driver (selenium.webdriver): Selenium WebDriver instance.
        credentials_from_params (tuple): Optional (username, password) tuple to use instead of .env
    
    Returns:
        bool: True if login is successful, False otherwise.
    """
    # Load credentials from parameters or environment
    if credentials_from_params and len(credentials_from_params) == 2:
        username, password = credentials_from_params
    else:
        # Load from environment
        load_dotenv()
        username = os.getenv("NAUKRI_USERNAME")
        password = os.getenv("NAUKRI_PASSWORD")
    
    if not username or not password:
        raise Exception("Naukri credentials not found. Please set NAUKRI_USERNAME and NAUKRI_PASSWORD in .env file or provide them as parameters.")
    
    # Navigate to login page
    print("Navigating to Naukri login page...")
    driver.get("https://www.naukri.com/nlogin/login")
    
    # Set up wait objects with increased timeouts
    short_wait = WebDriverWait(driver, 20)  # Increased timeout
    long_wait = WebDriverWait(driver, 180)  # Much longer timeout for OTP

    try:
        # Enter email/username
        print("Entering username...")
        email_field = short_wait.until(EC.presence_of_element_located((By.ID, "usernameField")))
        email_field.clear()
        email_field.send_keys(username)

        # Enter password
        print("Entering password...")
        password_field = short_wait.until(EC.presence_of_element_located((By.ID, "passwordField")))
        password_field.clear()
        password_field.send_keys(password)

        # Click login button
        print("Clicking login button...")
        login_button = short_wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']")))
        login_button.click()
        print("Credentials entered. Please complete OTP if prompted.")
    except Exception as e:
        print(f"Auto-fill failed, you may need to login manually: {e}")

    # Add a longer pause after clicking login
    print("Waiting for login to complete (this may take up to 3 minutes for OTP)...")
    time.sleep(5)

    # Wait for successful login
    print("Verifying login success...")
    try:
        long_wait.until(EC.url_contains("mnjuser"))
        print("Login verified! Reached mnjuser homepage.")
        return True
    except Exception as e:
        print(f"Login verification failed: {e}")
        return False

    except Exception as e:
        print(f"Login process failed: {e}")
        return False


def setup_credentials_interactive(headless=True):
    """
    Interactive command-line setup for Naukri credentials.
    Tests login before saving to .env file.
    
    Parameters:
        headless (bool): Whether to use headless mode for validation
        
    Returns:
        bool: True if credentials were successfully set up
    """
    print("\n=== Naukri Credentials Setup ===")
    print("Please enter your Naukri.com login information.")
    
    username = input("Email/Username: ").strip()
    password = input("Password: ").strip()
    
    if not username or not password:
        print("Both username and password are required.")
        return False
    
    # Validate the credentials
    if validate_naukri_credentials(username, password, headless=headless):
        # Save to .env file
        update_naukri_credentials(username, password)
        return True
    else:
        print("Invalid credentials. Please try again.")
        return False

if __name__ == "__main__":
    # This allows running the file directly for credential setup
    try:
        print("Starting Naukri credential setup...")
        success = False
        
        while not success:
            success = setup_credentials_interactive(headless=False)
            if not success:
                retry = input("Would you like to try again? (y/n): ").lower()
                if retry != 'y':
                    break
        
        if success:
            print("Credential setup complete! You can now run the main application.")
        else:
            print("Credential setup was not completed. You will need to set up credentials before using the application.")
    
    except Exception as e:
        print(f"An error occurred during setup: {e}")