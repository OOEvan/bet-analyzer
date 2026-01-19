# 🤖 Automated NFL Bet Finder Setup Guide

## Overview
This system automatically:
1. ✅ Scrapes player statistics from NFL.com/ESPN
2. ✅ Pulls live odds from FanDuel, DraftKings, and other books via The Odds API
3. ✅ Calculates projections and finds betting edges
4. ✅ Ranks best bets by expected value
5. ✅ Builds optimal parlays

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt --break-system-packages
```

### 2. Get The Odds API Key
1. Go to https://the-odds-api.com
2. Sign up for free account
3. Get your API key (500 requests/month free)
4. Copy your API key

### 3. Configure API Key
Open `api_server.py` and replace:
```python
API_KEY = "your_api_key_here"
```
With your actual key:
```python
API_KEY = "abc123your_actual_key"
```

### 4. Run the API Server
```bash
python api_server.py
```

The server will start on `http://localhost:5000`

## Usage Examples

### Quick Scan (Easiest)
```bash
curl http://localhost:5000/api/quick-scan
```

Returns top 20 best bets across popular players automatically!

### Custom Player Scan
```bash
curl -X POST http://localhost:5000/api/scan-best-bets \
  -H "Content-Type: application/json" \
  -d '{
    "players": [
      {"name": "Patrick Mahomes", "props": ["player_pass_yds", "player_pass_tds"]},
      {"name": "Jonathan Taylor", "props": ["player_rush_yds", "player_anytime_td"]}
    ],
    "min_edge": 5.0
  }'
```

### Get Player Stats
```bash
curl -X POST http://localhost:5000/api/get-player-stats \
  -H "Content-Type: application/json" \
  -d '{
    "player_name": "Patrick Mahomes",
    "stat_type": "passing_yards",
    "num_games": 7
  }'
```

### Get Current Odds
```bash
curl -X POST http://localhost:5000/api/get-odds \
  -H "Content-Type: application/json" \
  -d '{
    "player_name": "Patrick Mahomes",
    "prop_type": "player_pass_yds"
  }'
```

### Build Optimal Parlay
```bash
curl -X POST http://localhost:5000/api/build-parlay \
  -H "Content-Type: application/json" \
  -d '{
    "bets": [/* array of bet objects */],
    "num_legs": 3
  }'
```

## How It Works

### 1. Stats Scraping
The system can pull stats from multiple sources:
- **NFL.com** - Official stats (requires scraping or API)
- **ESPN** - Free API available
- **Pro Football Reference** - Easy to scrape
- **Mock Data** - Currently uses mock data for demonstration

### 2. Odds Scraping
Uses The Odds API to pull live odds from:
- FanDuel
- DraftKings
- BetMGM
- Caesars
- And 20+ other sportsbooks

### 3. Edge Calculation
For each bet:
```
Projection = Weighted Average of Recent Games
Hit Rate = % of games over/under the line
Edge = Projection - Sportsbook Line
Edge % = (Edge / Line) × 100
```

### 4. Ranking System
Bets are ranked by:
- Edge percentage (higher is better)
- Confidence level (High > Medium > Low)
- Hit rate consistency

## API Response Format

### Best Bets Response
```json
{
  "success": true,
  "bets": [
    {
      "player": "Patrick Mahomes",
      "prop_type": "player_pass_yds",
      "bet": "OVER",
      "line": 249.5,
      "odds": -110,
      "bookmaker": "FanDuel",
      "weighted_avg": 285.3,
      "hit_rate": 71.4,
      "edge": 35.8,
      "edge_percent": 14.3,
      "confidence": "High",
      "recommendation": "OVER"
    }
  ],
  "count": 15
}
```

## Upgrading to Production Stats

### Option 1: NFL Official API
```python
# Requires NFL API subscription
# https://api.nfl.com/docs/
```

### Option 2: ESPN API (Free)
```python
import requests

def get_espn_stats(player_id):
    url = f"https://site.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{player_id}/gamelog"
    response = requests.get(url)
    return response.json()
```

### Option 3: Pro Football Reference Scraping
```python
from bs4 import BeautifulSoup

def scrape_pfr_stats(player_url):
    # Scrape from pro-football-reference.com
    # More stable than NFL.com
    pass
```

### Option 4: Paid Services
- **SportsRadar** - Enterprise-grade data
- **Sportradar** - Real-time stats
- **RapidAPI Sports** - Multiple sports APIs

## Integration with HTML Interface

To connect to your HTML interface, update the JavaScript to call these endpoints:

```javascript
// In index.html, add a "Quick Scan" button
async function quickScan() {
    const response = await fetch('http://localhost:5000/api/quick-scan');
    const data = await response.json();
    
    // Display results
    data.bets.forEach(bet => {
        // Add to your interface
        console.log(`${bet.player} - ${bet.bet} ${bet.line} (${bet.edge_percent}% edge)`);
    });
}
```

## Rate Limiting

**The Odds API Free Tier:**
- 500 requests per month
- Resets monthly
- Each prop market = 1 request
- 7 markets × 10 players = 70 requests per scan

**Recommendation:**
- Run scans 2-3 times per day max
- Cache results for 1-2 hours
- Use database to track historical accuracy

## Database Schema

The system saves all found bets to SQLite:

```sql
CREATE TABLE best_bets (
    id INTEGER PRIMARY KEY,
    player_name TEXT,
    prop_type TEXT,
    line REAL,
    projection REAL,
    edge REAL,
    edge_percent REAL,
    hit_rate REAL,
    recommendation TEXT,
    confidence TEXT,
    bookmaker TEXT,
    odds INTEGER,
    created_at TIMESTAMP
);
```

## Performance Tips

1. **Cache Odds Data** - Don't fetch on every request
2. **Batch Player Analysis** - Analyze multiple players at once
3. **Pre-compute Stats** - Calculate projections ahead of time
4. **Use Redis** - For faster caching in production
5. **Async Requests** - Use `aiohttp` for parallel scraping

## Troubleshooting

### "API Key Invalid"
- Check your key at https://the-odds-api.com
- Make sure it's properly configured in api_server.py

### "No Stats Found"
- Currently using mock data
- Implement real scraping (see "Upgrading to Production Stats")

### "Rate Limit Exceeded"
- You've used your 500 monthly requests
- Wait for monthly reset or upgrade plan

### "CORS Error"
- Make sure Flask-CORS is installed
- API server must be running on localhost:5000

## Next Steps

1. ✅ Get API key and test quick scan
2. ✅ Implement real stats scraping (ESPN API recommended)
3. ✅ Add caching layer (Redis or SQLite)
4. ✅ Connect to HTML interface
5. ✅ Track bet results to measure accuracy
6. ✅ Build notification system for high-edge bets

## Support

For issues:
1. Check The Odds API status
2. Verify API key is valid
3. Test with curl first
4. Check Flask logs for errors

Happy betting! 🎰
