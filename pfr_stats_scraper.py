"""
Pro Football Reference Stats Scraper
Pulls REAL player game logs from pro-football-reference.com
More reliable than ESPN API and has complete historical data
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import time
import re


class PFRStatsScraper:
    """Scrape real player statistics from Pro Football Reference"""
    
    def __init__(self):
        self.base_url = "https://www.pro-football-reference.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.player_cache = {}
    
    def search_player(self, player_name: str) -> Optional[str]:
        """
        Search for a player and get their PFR ID
        Returns player URL slug (e.g., 'MahoPa00')
        """
        # Clean player name
        name_clean = player_name.strip().lower()
        
        # Try cache first
        if name_clean in self.player_cache:
            return self.player_cache[name_clean]
        
        try:
            # PFR search
            search_url = f"{self.base_url}/search/search.fcgi"
            params = {'search': player_name}
            
            response = requests.get(search_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            # If redirected directly to player page, extract ID from URL
            if '/players/' in response.url:
                player_id = response.url.split('/players/')[1].split('/')[1].replace('.htm', '')
                self.player_cache[name_clean] = player_id
                return player_id
            
            # Otherwise parse search results
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find first player result
            search_results = soup.find('div', {'id': 'players'})
            if search_results:
                first_result = search_results.find('div', {'class': 'search-item-name'})
                if first_result:
                    link = first_result.find('a')
                    if link and link.get('href'):
                        player_id = link['href'].split('/players/')[1].split('/')[1].replace('.htm', '')
                        self.player_cache[name_clean] = player_id
                        return player_id
            
            return None
            
        except Exception as e:
            print(f"  ⚠️  Search error: {str(e)[:100]}")
            return None
    
    def get_player_gamelog(self, player_id: str, season: int = 2025, stat_category: str = None) -> List[Dict]:
        """
        Get player's game log for the season
        Returns list of game stats dictionaries
        
        Args:
            stat_category: 'passing', 'rushing', 'receiving' to help find right table
        """
        try:
            url = f"{self.base_url}/players/{player_id[0]}/{player_id}/gamelog/{season}/"
            
            print(f"  📡 Fetching from: {url}")
            
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try to find the right table based on stat category
            table = None
            
            if stat_category == 'passing':
                # Try passing-specific tables first
                for table_id in ['passing', 'passing_advanced']:
                    table = soup.find('table', {'id': table_id})
                    if table:
                        print(f"  ✅ Found table: {table_id}")
                        break
            elif stat_category == 'rushing':
                # Try rushing tables
                for table_id in ['rushing_and_receiving', 'rushing']:
                    table = soup.find('table', {'id': table_id})
                    if table:
                        print(f"  ✅ Found table: {table_id}")
                        break
            elif stat_category == 'receiving':
                # Try receiving tables
                for table_id in ['receiving_and_rushing', 'rushing_and_receiving', 'receiving']:
                    table = soup.find('table', {'id': table_id})
                    if table:
                        print(f"  ✅ Found table: {table_id}")
                        break
            
            # Only use 'stats' as absolute last resort
            if not table:
                table = soup.find('table', {'id': 'stats'})
                if table:
                    print(f"  ⚠️  Using fallback table: stats")
            
            if not table:
                print(f"  ❌ Could not find any stats table")
                return []
            
            games = []
            tbody = table.find('tbody')
            
            if not tbody:
                print(f"  ⚠️  No tbody found")
                return []
            
            for row in tbody.find_all('tr'):
                # Skip header rows and dividers
                classes = row.get('class', [])
                if 'thead' in classes or 'over_header' in classes or 'stat_total' in classes:
                    continue
                    
                # Check if it's a bye week or divider by looking for reason text
                reason_cell = row.find('td', {'data-stat': 'reason'})
                if reason_cell:
                    reason_text = reason_cell.get_text(strip=True)
                    if reason_text:  # Has text like "Bye Week"
                        continue
                
                game = {}
                
                # Extract all stat cells from both th and td tags
                for cell in row.find_all(['th', 'td']):
                    stat_name = cell.get('data-stat')
                    stat_value = cell.get_text(strip=True)
                    
                    if stat_name and stat_value:
                        game[stat_name] = stat_value
                
                # Add if we have at least a few stats (not just empty row)
                if len(game) >= 3:
                    games.append(game)
            
            print(f"  📊 Found {len(games)} games total")
            if games:
                print(f"  📝 Sample stats from first game: {list(games[0].keys())[:10]}")
            
            return games
            
        except Exception as e:
            print(f"  ⚠️  Gamelog error: {str(e)[:200]}")
            return []
    
    def get_player_recent_games(self, player_name: str, stat_type: str, num_games: int = 7) -> List[float]:
        """
        Get player's recent game statistics
        
        Args:
            player_name: Player's full name
            stat_type: Type of stat (pass_yds, rush_yds, receptions, etc.)
            num_games: Number of recent games to fetch
        
        Returns:
            List of stat values from recent games (most recent first)
        """
        print(f"🔍 Fetching real stats for {player_name} - {stat_type}...")
        
        # Get player ID
        player_id = self.search_player(player_name)
        
        if not player_id:
            print(f"  ❌ Player not found on PFR")
            return []
        
        # Determine stat category for table lookup
        stat_category = None
        if stat_type in ['pass_yds', 'passing_yards', 'pass_tds', 'passing_tds']:
            stat_category = 'passing'
        elif stat_type in ['rush_yds', 'rushing_yards', 'rush_tds', 'rushing_tds']:
            stat_category = 'rushing'
        elif stat_type in ['receptions', 'reception_yds', 'receiving_yards', 'rec_tds', 'receiving_tds']:
            stat_category = 'receiving'
        
        # Get game log
        all_games = self.get_player_gamelog(player_id, stat_category=stat_category)
        
        if not all_games:
            print(f"  ❌ No game data found")
            return []
        
        # PFR lists games from OLDEST to NEWEST
        # So we need to reverse the list first, then take the most recent games
        all_games.reverse()
        
        # Map stat types to PFR column names
        stat_map = {
            'pass_yds': 'pass_yds',
            'passing_yards': 'pass_yds',
            'pass_tds': 'pass_td',
            'passing_tds': 'pass_td',
            
            'rush_yds': 'rush_yds',
            'rushing_yards': 'rush_yds',
            'rush_tds': 'rush_td',
            'rushing_tds': 'rush_td',
            
            'receptions': 'rec',
            'reception_yds': 'rec_yds',
            'receiving_yards': 'rec_yds',
            'rec_tds': 'rec_td',
            'receiving_tds': 'rec_td',
        }
        
        pfr_stat = stat_map.get(stat_type)
        
        if not pfr_stat:
            print(f"  ⚠️  Unknown stat type: {stat_type}")
            return []
        
        # Extract stats from most recent games
        stats = []
        for game in all_games[:num_games]:
            stat_value = game.get(pfr_stat, '0')
            
            # Clean the value (remove commas, handle empty)
            try:
                stat_value = stat_value.replace(',', '')
                value = float(stat_value) if stat_value else 0.0
                stats.append(value)
            except ValueError:
                stats.append(0.0)
        
        if stats:
            print(f"  ✅ Found {len(stats)} games: {stats}")
            return stats
        else:
            print(f"  ⚠️  No {stat_type} stats found")
            return []


# ============================================================================
# TEST THE SCRAPER
# ============================================================================

if __name__ == "__main__":
    
    scraper = PFRStatsScraper()
    
    print("="*80)
    print("🏈 PRO FOOTBALL REFERENCE SCRAPER TEST")
    print("="*80)
    
    # Test with various players
    test_players = [
        ('Christian McCaffrey', 'rush_yds'),
        ('Brock Purdy', 'rush_yds'),
        ('Justin Jefferson', 'receptions'),
        ('Patrick Mahomes', 'pass_yds'),
        ('Saquon Barkley', 'rush_yds'),
    ]
    
    for player_name, stat_type in test_players:
        print(f"\n{'='*80}")
        print(f"Testing: {player_name} - {stat_type}")
        print('='*80)
        
        stats = scraper.get_player_recent_games(player_name, stat_type, num_games=7)
        
        if stats:
            avg = sum(stats) / len(stats)
            print(f"\nAverage: {avg:.1f}")
            print(f"Min: {min(stats):.1f} | Max: {max(stats):.1f}")
        else:
            print("\nNo stats found - player may not be active or name incorrect")
        
        time.sleep(2)  # Be nice to PFR's servers
    
    print("\n" + "="*80)
    print("✅ Test complete!")
    print("="*80)
