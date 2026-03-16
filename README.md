# Naukri Auto-Apply Bot

This application automates the job application process on Naukri.com. It features a graphical user interface (GUI) to help students and job seekers manage their applications without needing advanced technical knowledge.

## Installation and Setup

### 1. Clone the Repository

Run these commands in your terminal:

```bash
git clone https://github.com/ychaitu2025-dot/auto-apply-naukri-jobs.git
cd auto-apply-naukri-jobs

```

### 2. Create a Virtual Environment

This keeps the project dependencies organized and separate from your system.

For Windows:

```bash
python -m venv venv
venv\Scripts\activate

```

For macOS / Linux:

```bash
python3 -m venv venv
source venv/bin/activate

```

### 3. Install Required Packages

Install the libraries needed for the bot to function:

```bash
pip install -r requirements.txt

```

### 4. Configure Your Credentials

1. Find the file named .env.sample and rename it to .env
2. Open .env in a text editor and enter your Naukri details:
NAUKRI_USERNAME='your_email@example.com'
NAUKRI_PASSWORD='your_password'

Note: If you are on Linux (Ubuntu/Debian), you may need to install the windowing toolkit:

```bash
sudo apt-get install python3-tk

```

## Running the Application

To start the bot, run the following command in your terminal:

For Windows:

```bash
python run.py

```

For macOS / Linux:

```bash
python3 run.py

```

## Browser Support

The application automatically detects and uses your installed browsers in this order of preference:

1. Brave Browser (Recommended)
2. Google Chrome
3. Safari (macOS only)
4. Microsoft Edge
5. Firefox

## How to Use

1. Settings Tab: Enter and test your Naukri login credentials.
2. Job Filters: Enter the job titles you are looking for. You can also add keywords to include or exclude (e.g., exclude "Internship" if you want full-time roles).
3. Limits: Set the maximum number of jobs you want the bot to apply for in one session.
4. Run Bot: Click Save Settings, navigate to the Run Bot tab, and click start.

The application will generate Excel files summarizing which jobs were applied for and which were skipped based on your filters.

## Troubleshooting

* If the login fails due to a slow internet connection, increase the timeout duration in the Settings tab.
* If you encounter browser driver errors, ensure you are using the run.py script, as it automatically manages driver permissions.
