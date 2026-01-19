"""
NBA Stats & Odds Integration
Works alongside your existing NFL bet finder
"""

import requests
from bs4 import BeautifulSoup
import time
import statistics
from typing import List, Dict, Optional

# ============================================================================
# NBA STATS SCRAPER - Basketball Reference
# ============================================================================

class NBAStatsScraper:
    """Scrape player stats from Basketball Reference"""
    
    def __init__(self):
        self.base_url = "https://www.basketball-reference.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def get_player_recent_games(self, player_name: str, stat_type: str, num_games: int = 7) -> List[float]:
        """Get recent game stats for a player"""
        try:
            # Search for player
            search_url = f"{self.base_url}/search/search.fcgi?search={player_name.replace(' ', '+')}"
            response = requests.get(search_url, headers=self.headers)
            time.sleep(1)
            
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            search_results = soup.find('div', {'class': 'search-item-name'})
            if not search_results:
                return []
            
            player_link = search_results.find('a')
            if not player_link:
                return []
            
            # Get player ID and construct gamelog URL
            player_id = player_link['href'].split('/')[-1].replace('.html', '')
            gamelog_url = f"{self.base_url}/players/{player_id[0]}/{player_id}/gamelog/2025"
            
            response = requests.get(gamelog_url, headers=self.headers)
            time.sleep(1)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            gamelog_table = soup.find('table', {'id': 'pgl_basic'})
            
            if not gamelog_table:
                return []
            
            # Map stat types to table columns
            stat_mapping = {
                'points': 'pts',
                'rebounds': 'trb',
                'assists': 'ast',
                'threes': 'fg3',
                'steals': 'stl',
                'blocks': 'blk'
            }
            
            stat_col = stat_mapping.get(stat_type, stat_type)
            
            rows = gamelog_table.find('tbody').find_all('tr', {'class': lambda x: x != 'thead'})
            
            recent_stats = []
            count = 0
            for row in reversed(rows):
                if count >= num_games:
                    break
                
                if row.find('th', {'data-stat': 'ranker'}):
                    stat_cell = row.find('td', {'data-stat': stat_col})
                    if stat_cell and stat_cell.text.strip():
                        try:
                            recent_stats.append(float(stat_cell.text.strip()))
                            count += 1
                        except ValueError:
                            continue
            
            return recent_stats
            
        except Exception as e:
            print(f"Error scraping NBA stats for {player_name}: {e}")
            return []
    
    def get_season_average(self, player_name: str, stat_type: str) -> Optional[float]:
        """Get season average for a stat"""
        try:
            recent_games = self.get_player_recent_games(player_name, stat_type, num_games=20)
            if recent_games:
                return statistics.mean(recent_games)
            return None
        except:
            return None


# ============================================================================
# NBA ODDS SCRAPER
# ============================================================================

class NBAOddsScraper:
    """Fetch NBA player props from The Odds API"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.the-odds-api.com/v4"
        self.sport = "basketball_nba"
    
    def get_all_events(self) -> List[Dict]:
        """Get all upcoming NBA games"""
        endpoint = f"{self.base_url}/sports/{self.sport}/events"
        params = {'apiKey': self.api_key}
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            events = response.json()
            print(f"✅ Found {len(events)} upcoming NBA games")
            return events
        except Exception as e:
            print(f"❌ Error fetching NBA events: {e}")
            return []
    
    def get_all_player_props(self) -> Dict:
        """Fetch all NBA player prop markets"""
        events = self.get_all_events()
        
        if not events:
            return {}
        
        markets = [
            'player_points',
            'player_rebounds',
            'player_assists',
            'player_threes',
            'player_blocks',
            'player_steals'
        ]
        
        all_props = {}
        
        for event in events[:5]:  # Limit to save API calls
            event_id = event['id']
            event_name = f"{event['home_team']} vs {event['away_team']}"
            print(f"\n🏀 Fetching props for: {event_name}")
            
            event_props = {}
            
            for market in markets:
                props = self._fetch_event_market(event_id, market)
                if props:
                    event_props[market] = props
                    player_count = self._count_players_in_market(props)
                    print(f"  ✓ {market}: {player_count} players")
                time.sleep(0.5)
            
            all_props[event_id] = {
                'event_name': event_name,
                'home_team': event['home_team'],
                'away_team': event['away_team'],
                'commence_time': event['commence_time'],
                'props': event_props
            }
        
        return all_props
    
    def _fetch_event_market(self, event_id: str, market: str) -> Optional[Dict]:
        """Fetch specific market for an event"""
        endpoint = f"{self.base_url}/sports/{self.sport}/events/{event_id}/odds"
        
        params = {
            'apiKey': self.api_key,
            'regions': 'us',
            'markets': market,
            'oddsFormat': 'american'
        }
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"  ⚠️  Failed to fetch {market}: {e}")
            return None
    
    def _count_players_in_market(self, props_data: Dict) -> int:
        """Count unique players in market"""
        if not props_data or 'bookmakers' not in props_data:
            return 0
        
        players = set()
        for bookmaker in props_data.get('bookmakers', []):
            for market in bookmaker.get('markets', []):
                for outcome in market.get('outcomes', []):
                    players.add(outcome.get('description', ''))
        
        return len(players)
    
    def get_best_line(self, props_data: Dict, player_name: str) -> Optional[Dict]:
        """Get best available line for a player"""
        if not props_data or 'bookmakers' not in props_data:
            return None
        
        best_over = None
        best_under = None
        
        for bookmaker in props_data.get('bookmakers', []):
            for market in bookmaker.get('markets', []):
                for outcome in market.get('outcomes', []):
                    if outcome.get('description', '') == player_name:
                        line = outcome.get('point')
                        price = outcome.get('price')
                        name = outcome.get('name')
                        
                        if name == 'Over':
                            if not best_over or price > best_over['price']:
                                best_over = {
                                    'line': line,
                                    'price': price,
                                    'bookmaker': bookmaker.get('key', '')
                                }
                        elif name == 'Under':
                            if not best_under or price > best_under['price']:
                                best_under = {
                                    'line': line,
                                    'price': price,
                                    'bookmaker': bookmaker.get('key', '')
                                }
        
        return {
            'over': best_over,
            'under': best_under
        }


# ============================================================================
# NBA EDGE CALCULATOR
# ============================================================================

class NBAEdgeCalculator:
    """Calculate betting edges for NBA props"""
    
    def __init__(self, stats_scraper: NBAStatsScraper):
        self.stats_scraper = stats_scraper
    
    def calculate_edge(self, player_name: str, stat_type: str, line: float, 
                       odds: int, num_games: int = 7) -> Optional[Dict]:
        """Calculate edge for a player prop"""
        
        print(f"  🔍 Calculating edge for {player_name} - {stat_type} {line}")
        
        # Get recent stats
        recent_stats = self.stats_scraper.get_player_recent_games(
            player_name, stat_type, num_games
        )
        
        if not recent_stats or len(recent_stats) < 3:
            print(f"    ❌ Not enough stats for {player_name} ({len(recent_stats) if recent_stats else 0} games found)")
            return None
        
        # Calculate average and std dev
        avg = statistics.mean(recent_stats)
        std_dev = statistics.stdev(recent_stats) if len(recent_stats) > 1 else avg * 0.3
        
        print(f"    📊 Recent games: {recent_stats}")
        print(f"    📊 Average: {avg:.1f}, Line: {line}")
        
        # Calculate hit rate (simple method)
        hits_over = sum(1 for stat in recent_stats if stat > line)
        hit_rate_over = hits_over / len(recent_stats)
        hit_rate_under = 1 - hit_rate_over
        
        # Convert American odds to implied probability
        if odds < 0:
            implied_prob = -odds / (-odds + 100)
        else:
            implied_prob = 100 / (odds + 100)
        
        # Calculate edge
        edge = hit_rate_over - implied_prob
        edge_pct = edge * 100
        
        print(f"    📈 Hit rate: {hit_rate_over*100:.1f}%, Implied prob: {implied_prob*100:.1f}%, Edge: {edge_pct:.2f}%")
        
        return {
            'player': player_name,
            'stat_type': stat_type,
            'line': line,
            'odds': odds,
            'recent_avg': round(avg, 2),
            'hit_rate': round(hit_rate_over * 100, 1),
            'implied_prob': round(implied_prob * 100, 1),
            'edge': round(edge_pct, 2),
            'recent_games': recent_stats
        }
