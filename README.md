# Content Monitoring System

Hey there! This is a little project I put together to keep an eye on content changes across LinkedIn profiles, company pages, and websites. It uses some AI magic to figure out if something actually changed in a meaningful way, and it can send you notifications when it does. Built with LangGraph to coordinate a bunch of agents that handle the scraping, analyzing, and notifying.

## Getting Started

First off, make sure you have Python installed. Then:

1. Grab the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Fire it up:
   ```bash
   python main.py start
   ```

3. Head over to http://localhost:8000 in your browser to start adding stuff to monitor.

## What It Does

- Keeps tabs on LinkedIn profiles, company pages, and regular websites
- Uses Google's Gemini AI to spot real changes (not just minor tweaks)
- Sends you alerts via console or email
- Has a simple web dashboard for managing what you're watching
- Lets you set how often to check each site

## How It's Built

The system runs on five main agents orchestrated by LangGraph:

1. **Scheduler** - Figures out what needs checking and when
2. **Scraper** - Grabs the latest content from URLs
3. **Analyzer** - Uses AI to compare old vs. new content
4. **Notifier** - Shoots off alerts when changes are found
5. **Coordinator** - Keeps everything running smoothly

## Setup

You'll need to set up some environment variables in a `.env` file:

```env
# Must-haves
GEMINI_API_KEY=your_gemini_api_key_here
MONGODB_URI=your_mongodb_connection_string

# Nice-to-haves
REDIS_URL=your_redis_url_if_you_have_one
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
```

## Using It

### Adding Things to Monitor
- Go to http://localhost:8000
- Hit the "Add Target" section
- Paste in a URL and pick what type it is (LinkedIn profile/company or just a website)
- Choose how often you want to check it
- Hit "Add Target"

### Seeing Changes
- Check the "Recent Changes" tab for updates
- Watch the console for live notifications
- Set up email alerts if you configured SMTP

## Running Modes

You can run different parts separately if you want:

```bash
# Everything at once (API, worker, scheduler)
python main.py start

# Just the web API
python main.py api

# Just the background worker
python main.py worker

# Just the scheduler
python main.py beat

# Run one check manually
python main.py monitor

# Test it out
python test_monitoring.py
```

## API Stuff

If you want to integrate with other tools:

- `POST /targets` - Add something to monitor
- `GET /targets` - List what's being monitored
- `DELETE /targets/{url}` - Stop monitoring something
- `GET /changes` - See recent changes
- `GET /health` - Check if everything's running

## Data Storage

Uses MongoDB with these collections:
- **targets** - Your monitoring settings
- **changes** - What changed and when
- **users** - If you add user accounts later

## Tech Under the Hood

- **LangGraph** - Handles the agent coordination
- **Python 3.10+** - The main language
- **MongoDB** - Stores everything
- **Celery + Redis** - Runs the scheduled checks
- **Google Gemini** - Does the smart change detection
- **FastAPI** - Powers the web interface
- **BeautifulSoup** - Scrapes web content

## How It Actually Works

1. The scheduler picks targets that are due for a check
2. The scraper pulls the current content
3. The analyzer compares it to what was there before using AI
4. If something meaningful changed, the notifier sends alerts
5. The coordinator keeps the whole process flowing

## A Few Notes

- LinkedIn might block scraping sometimes, so be nice
- You'll need a Gemini API key for the AI analysis
- Email alerts require SMTP setup
- It saves snapshots of content to compare against
- You can set different check frequencies for each target

Hope this helps you keep track of things! Let me know if you run into issues.