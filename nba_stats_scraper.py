"""
Basketball Reference NBA Stats Scraper
Fetches player stats with NO API rate limits
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)
CORS(app)

def find_player_id(player_name):
    """
    Find Basketball Reference player ID from name
    Uses search page to find player
    """
    try:
        # Basketball Reference search
        search_url = "https://www.basketball-reference.com/search/search.fcgi"
        params = {'search': player_name}
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(search_url, params=params, headers=headers, timeout=10)
        
        # If direct match, we get redirected to player page
        if '/players/' in response.url:
            # Extract ID from URL
            # URL format: /players/d/doncilu01.html
            player_id = response.url.split('/players/')[1].split('.html')[0]
            return player_id
        
        # If multiple matches, parse search results
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for search results
        search_item = soup.find('div', {'class': 'search-item-name'})
        if search_item:
            a_tag = search_item.find('a')
            if a_tag and 'href' in a_tag.attrs:
                href = a_tag['href']  # /players/d/doncilu01.html
                if '/players/' in href:
                    player_id = href.split('/players/')[1].split('.html')[0]
                    return player_id
        
        return None
        
    except Exception as e:
        print(f"Error finding player ID: {e}")
        return None


def scrape_game_log(player_id, stat_type):
    """
    Scrape player's game log from Basketball Reference
    Returns last 7 games of stats
    """
    try:
        # Current season is 2025-26, labeled as 2026 on Basketball Reference
        url = f"https://www.basketball-reference.com/players/{player_id}/gamelog/2026"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find game log table
        table = soup.find('table', {'id': 'pgl_basic'})
        
        if not table:
            return None
        
        # Column mapping for stats
        stat_columns = {
            'points': 'pts',
            'assists': 'ast',
            'rebounds': 'trb',  # Total rebounds
            'threes': 'fg3',     # 3-pointers made
            'blocks': 'blk',
            'steals': 'stl'
        }
        
        col_name = stat_columns.get(stat_type)
        if not col_name:
            return None
        
        # Extract last 7 games
        tbody = table.find('tbody')
        if not tbody:
            return None
            
        rows = tbody.find_all('tr', limit=10)  # Get more than 7 in case some are DNP
        
        games = []
        minutes = []
        
        for row in rows:
            # Skip rows that aren't games (like headers or "Did Not Play")
            if row.get('class') and 'thead' in row.get('class'):
                continue
            
            # Check if it was a real game (has stat data)
            stat_cell = row.find('td', {'data-stat': col_name})
            if not stat_cell or not stat_cell.text.strip():
                continue
            
            # Get stat value
            try:
                stat_value = float(stat_cell.text.strip())
                games.append(stat_value)
            except (ValueError, AttributeError):
                continue
            
            # Get minutes played
            min_cell = row.find('td', {'data-stat': 'mp'})
            if min_cell and min_cell.text.strip():
                # Minutes format: "35:24" → convert to 35.4
                min_text = min_cell.text.strip()
                if ':' in min_text:
                    min_parts = min_text.split(':')
                    min_value = int(min_parts[0])
                    if len(min_parts) > 1:
                        min_value += int(min_parts[1]) / 60
                    minutes.append(round(min_value, 1))
                else:
                    # Sometimes it's just a number
                    try:
                        minutes.append(float(min_text))
                    except:
                        minutes.append(0)
            else:
                minutes.append(0)
            
            # Stop after 7 games
            if len(games) >= 7:
                break
        
        return {
            'games': games[:7],
            'minutes': minutes[:7]
        }
        
    except Exception as e:
        print(f"Error scraping game log: {e}")
        return None


@app.route('/api/fetch-nba-stats', methods=['POST'])
def fetch_nba_stats():
    """
    Fetch NBA player stats from Basketball Reference
    NO API RATE LIMITS - Unlimited usage!
    """
    try:
        data = request.json
        player_name = data.get('player_name')
        stat_type = data.get('stat_type')
        
        if not player_name or not stat_type:
            return jsonify({
                'success': False,
                'error': 'Missing player_name or stat_type'
            })
        
        # Step 1: Find player ID
        print(f"Searching for player: {player_name}")
        player_id = find_player_id(player_name)
        
        if not player_id:
            return jsonify({
                'success': False,
                'error': f'Could not find player: {player_name}. Try full name (e.g., "LeBron James")'
            })
        
        print(f"Found player ID: {player_id}")
        
        # Step 2: Scrape game log (2025-26 season)
        result = scrape_game_log(player_id, stat_type)
        
        if not result:
            return jsonify({
                'success': False,
                'error': f'Could not fetch game log for {player_name}'
            })
        
        return jsonify({
            'success': True,
            'player': player_name,
            'games': result['games'],
            'minutes': result['minutes'],
            'source': 'Basketball-Reference.com',
            'url': f'https://www.basketball-reference.com/players/{player_id}/gamelog/2026'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


if __name__ == '__main__':
    # Test the scraper
    print("Testing Basketball Reference scraper...")
    
    test_players = [
        ("Luka Doncic", "points"),
        ("LeBron James", "assists"),
        ("Anthony Davis", "rebounds")
    ]
    
    for player, stat in test_players:
        print(f"\n--- Testing {player} {stat} ---")
        player_id = find_player_id(player)
        if player_id:
            print(f"Player ID: {player_id}")
            result = scrape_game_log(player_id, stat)
            if result:
                print(f"Stats: {result['games']}")
                print(f"Minutes: {result['minutes']}")
            else:
                print("Failed to scrape game log")
        else:
            print("Player not found")
    
    # To run as Flask server:
    # app.run(port=5000, debug=True)
