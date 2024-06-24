# Local Blackout Monitor (Ukraine)

This project monitors the electricity status for a local area, comparing the actual state with an expected schedule. It uses either the UptimeRobot API or web scraping to determine the current electricity status.

## Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/local-blackout-monitor.git
   cd local-blackout-monitor
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Set up your environment variables:
   - Copy `.env.example` to `.env`
   - Fill in your specific values in the `.env` file

4. Run the script:

   ```bash
   python localBlackoutMonitor.py
   ```

## Configuration

Edit the .env file with your specific settings:

- `GROUP_NUMBER`: Your outage group number
- `URL_HOUSE_STATE`: URL for scraping the current electricity status
- `DTEK_URL`: URL for fetching stable outage information
- `UPTIMEROBOT_API_KEY`: Your UptimeRobot API key (if using API method)
