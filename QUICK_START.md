# Quick Start: Enhanced Bet Analysis

## Files to Copy

```bash
cp enhanced_bet_analysis.py ~/nfl_betting/
cp api_server_UPDATED.py ~/nfl_betting/api_server.py
cp automated_web_app_UPDATED.html ~/nfl_betting/automated_web_app.html

cd ~/nfl_betting
python api_server.py
```

## What's New

Every bet now shows:
- Reliability Score (0-100)
- Consistency Score
- Backup player warnings
- CV% (variance)

## Reliability Ratings

- 85-100 = Elite (use in Conservative)
- 70-84 = High (use in Balanced)
- 55-69 = Medium (Aggressive only)
- Below 55 = Avoid in parlays

## Your Parlay Results Explained

Conservative (3/4 hit):
- Brian Robinson missed because he's a BACKUP RB
- New tool would filter him out automatically
- Expected: 4/4 or 3/3 with filtering

Aggressive (0/4):
- AJ Barner is a BACKUP TE
- George Kittle has high variance (CV 69%)
- Both now flagged with warnings

## Strategy

Start with 2-leg parlays:
- 85+ reliability each leg
- No backups
- Max 2 from same game
- Expected 80%+ hit rate per leg
