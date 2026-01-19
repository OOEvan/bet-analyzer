"""
NFL Defense Stats Scraper
Scrapes defensive rankings from Pro Football Reference
Used to adjust player projections based on opponent strength
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional
import time


class DefenseStatsScraper:
    """Scrape NFL defensive rankings from Pro Football Reference"""
    
    def __init__(self):
        self.base_url = "https://www.pro-football-reference.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        self.defense_cache = {}
        self.cache_timestamp = 0
    
    def get_defensive_rankings(self, season: int = 2025) -> Dict[str, Dict]:
        """
        Get defensive rankings for all teams
        Returns dict with team abbreviation as key
        """
        # Use cache if less than 1 hour old
        current_time = time.time()
        if self.defense_cache and (current_time - self.cache_timestamp) < 3600:
            return self.defense_cache
        
        try:
            url = f"{self.base_url}/years/{season}/opp.htm"
            
            print(f"🔍 Fetching defensive rankings from {url}")
            
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the team defense table
            table = soup.find('table', {'id': 'team_stats'})
            if not table:
                print("  ⚠️  Could not find defense stats table")
                return {}
            
            rankings = {}
            tbody = table.find('tbody')
            
            if not tbody:
                return {}
            
            rank = 1
            for row in tbody.find_all('tr'):
                # Skip header rows
                if row.find('th', {'class': 'over_header'}):
                    continue
                
                # Get team name/abbreviation - check both th and td
                team_cell = row.find('th', {'data-stat': 'team'})
                if not team_cell:
                    team_cell = row.find('td', {'data-stat': 'team'})
                
                if not team_cell:
                    continue
                
                team_name = team_cell.get_text(strip=True)
                team_link = team_cell.find('a')
                team_abbr = None
                
                if team_link and team_link.get('href'):
                    # Extract abbreviation from URL like /teams/dal/2025.htm
                    href = team_link['href']
                    parts = href.split('/')
                    if len(parts) >= 3:
                        team_abbr = parts[2].upper()
                
                # If no link, try to extract abbreviation from team name
                if not team_abbr:
                    # Map full names to abbreviations
                    name_to_abbr = {
                        'arizona cardinals': 'ARI',
                        'atlanta falcons': 'ATL',
                        'baltimore ravens': 'BAL',
                        'buffalo bills': 'BUF',
                        'carolina panthers': 'CAR',
                        'chicago bears': 'CHI',
                        'cincinnati bengals': 'CIN',
                        'cleveland browns': 'CLE',
                        'dallas cowboys': 'DAL',
                        'denver broncos': 'DEN',
                        'detroit lions': 'DET',
                        'green bay packers': 'GB',
                        'houston texans': 'HOU',
                        'indianapolis colts': 'IND',
                        'jacksonville jaguars': 'JAX',
                        'kansas city chiefs': 'KC',
                        'las vegas raiders': 'LV',
                        'los angeles chargers': 'LAC',
                        'los angeles rams': 'LAR',
                        'miami dolphins': 'MIA',
                        'minnesota vikings': 'MIN',
                        'new england patriots': 'NE',
                        'new orleans saints': 'NO',
                        'new york giants': 'NYG',
                        'new york jets': 'NYJ',
                        'philadelphia eagles': 'PHI',
                        'pittsburgh steelers': 'PIT',
                        'san francisco 49ers': 'SF',
                        'seattle seahawks': 'SEA',
                        'tampa bay buccaneers': 'TB',
                        'tennessee titans': 'TEN',
                        'washington commanders': 'WAS',
                    }
                    team_abbr = name_to_abbr.get(team_name.lower())
                
                # Get defensive stats
                pass_yds = row.find('td', {'data-stat': 'pass_yds'})
                rush_yds = row.find('td', {'data-stat': 'rush_yds'})
                points = row.find('td', {'data-stat': 'points'})
                
                pass_yds_val = float(pass_yds.get_text(strip=True)) if pass_yds else 0
                rush_yds_val = float(rush_yds.get_text(strip=True)) if rush_yds else 0
                points_val = float(points.get_text(strip=True)) if points else 0
                
                if team_abbr:
                    rankings[team_abbr] = {
                        'team_name': team_name,
                        'rank': rank,
                        'pass_yds_allowed': pass_yds_val,
                        'rush_yds_allowed': rush_yds_val,
                        'points_allowed': points_val
                    }
                    rank += 1
            
            print(f"  ✅ Loaded rankings for {len(rankings)} teams")
            
            # Cache the results
            self.defense_cache = rankings
            self.cache_timestamp = current_time
            
            return rankings
            
        except Exception as e:
            print(f"  ⚠️  Error fetching defense rankings: {str(e)[:100]}")
            return {}
    
    def get_matchup_adjustment(self, opponent: str, stat_type: str) -> float:
        """
        Get adjustment factor for a specific opponent matchup
        
        Args:
            opponent: Team abbreviation (e.g., 'PHI', 'DAL')
            stat_type: Type of stat (pass_yds, rush_yds, etc.)
        
        Returns:
            Adjustment multiplier (e.g., 0.85 for -15%, 1.15 for +15%)
        """
        opponent = opponent.upper().strip()
        
        # Get rankings
        rankings = self.get_defensive_rankings()
        
        if not rankings or opponent not in rankings:
            print(f"  ⚠️  No defensive data for {opponent}, using neutral adjustment")
            return 1.0  # No adjustment
        
        defense = rankings[opponent]
        rank = defense['rank']
        total_teams = len(rankings)
        
        # Determine if opponent is elite, average, or poor defense
        if stat_type in ['pass_yds', 'passing_yards', 'pass_tds', 'passing_tds']:
            # Passing defense
            stat_value = defense['pass_yds_allowed']
            
            # Lower yards allowed = better defense = tougher matchup
            # Top 10 teams (elite defense)
            if rank <= 10:
                adjustment = 0.85  # -15% for elite pass defense
                tier = "Elite"
            # Bottom 10 teams (poor defense)
            elif rank >= total_teams - 9:
                adjustment = 1.15  # +15% for poor pass defense
                tier = "Poor"
            # Middle teams
            else:
                adjustment = 1.0  # No adjustment
                tier = "Average"
            
            print(f"  📊 {opponent} pass defense: Rank {rank}/{total_teams} ({tier}) - {adjustment}x adjustment")
            
        elif stat_type in ['rush_yds', 'rushing_yards', 'rush_tds', 'rushing_tds']:
            # Rushing defense
            stat_value = defense['rush_yds_allowed']
            
            if rank <= 10:
                adjustment = 0.85  # -15% for elite run defense
                tier = "Elite"
            elif rank >= total_teams - 9:
                adjustment = 1.15  # +15% for poor run defense
                tier = "Poor"
            else:
                adjustment = 1.0
                tier = "Average"
            
            print(f"  📊 {opponent} run defense: Rank {rank}/{total_teams} ({tier}) - {adjustment}x adjustment")
            
        elif stat_type in ['receptions', 'reception_yds', 'receiving_yards', 'rec_tds', 'receiving_tds']:
            # Receiving uses pass defense ranking
            stat_value = defense['pass_yds_allowed']
            
            if rank <= 10:
                adjustment = 0.88  # -12% for elite pass defense (slightly less than QB)
                tier = "Elite"
            elif rank >= total_teams - 9:
                adjustment = 1.12  # +12% for poor pass defense
                tier = "Poor"
            else:
                adjustment = 1.0
                tier = "Average"
            
            print(f"  📊 {opponent} pass defense: Rank {rank}/{total_teams} ({tier}) - {adjustment}x adjustment")
            
        else:
            adjustment = 1.0
            print(f"  ⚠️  Unknown stat type: {stat_type}, no adjustment")
        
        return adjustment


# ============================================================================
# TEST THE SCRAPER
# ============================================================================

if __name__ == "__main__":
    
    scraper = DefenseStatsScraper()
    
    print("="*80)
    print("🏈 DEFENSE STATS SCRAPER TEST")
    print("="*80)
    
    # Test getting rankings
    rankings = scraper.get_defensive_rankings()
    
    if rankings:
        print(f"\n✅ Loaded {len(rankings)} teams")
        print("\nTop 5 Pass Defenses:")
        sorted_teams = sorted(rankings.items(), key=lambda x: x[1]['pass_yds_allowed'])
        for i, (abbr, data) in enumerate(sorted_teams[:5]):
            print(f"  {i+1}. {abbr} ({data['team_name']}): {data['pass_yds_allowed']:.1f} yds/game")
        
        print("\nBottom 5 Pass Defenses:")
        for i, (abbr, data) in enumerate(sorted_teams[-5:]):
            print(f"  {len(sorted_teams)-4+i}. {abbr} ({data['team_name']}): {data['pass_yds_allowed']:.1f} yds/game")
    
    print("\n" + "="*80)
    print("Testing Matchup Adjustments")
    print("="*80)
    
    # Test some matchups
    test_matchups = [
        ('PHI', 'pass_yds'),  # Eagles pass defense
        ('DAL', 'pass_yds'),  # Cowboys pass defense
        ('KC', 'rush_yds'),   # Chiefs run defense
    ]
    
    for opponent, stat_type in test_matchups:
        print(f"\n{opponent} vs {stat_type}:")
        adjustment = scraper.get_matchup_adjustment(opponent, stat_type)
        print(f"  Final adjustment: {adjustment}x")
        print(f"  Example: 300 yards → {300 * adjustment:.1f} yards")
    
    print("\n" + "="*80)
    print("✅ Test complete!")
    print("="*80)
