"""
Weather and Venue Scraper
Fetches weather conditions and venue type (dome vs outdoor) for NFL games
Used to adjust player projections based on game conditions
"""

import requests
from typing import Dict, Optional
import time


class WeatherVenueScraper:
    """Scrape weather and venue information for NFL games"""
    
    def __init__(self):
        self.cache = {}
        self.cache_timestamp = {}
        
        # NFL Stadiums - Dome vs Outdoor
        self.stadiums = {
            # Domes (retractable roofs closed in bad weather)
            'Arizona Cardinals': {'type': 'dome', 'city': 'Glendale', 'state': 'AZ'},
            'Atlanta Falcons': {'type': 'dome', 'city': 'Atlanta', 'state': 'GA'},
            'Dallas Cowboys': {'type': 'dome', 'city': 'Arlington', 'state': 'TX'},
            'Detroit Lions': {'type': 'dome', 'city': 'Detroit', 'state': 'MI'},
            'Houston Texans': {'type': 'dome', 'city': 'Houston', 'state': 'TX'},
            'Indianapolis Colts': {'type': 'dome', 'city': 'Indianapolis', 'state': 'IN'},
            'Las Vegas Raiders': {'type': 'dome', 'city': 'Las Vegas', 'state': 'NV'},
            'Los Angeles Chargers': {'type': 'dome', 'city': 'Inglewood', 'state': 'CA'},
            'Los Angeles Rams': {'type': 'dome', 'city': 'Inglewood', 'state': 'CA'},
            'Minnesota Vikings': {'type': 'dome', 'city': 'Minneapolis', 'state': 'MN'},
            'New Orleans Saints': {'type': 'dome', 'city': 'New Orleans', 'state': 'LA'},
            
            # Outdoor stadiums
            'Baltimore Ravens': {'type': 'outdoor', 'city': 'Baltimore', 'state': 'MD'},
            'Buffalo Bills': {'type': 'outdoor', 'city': 'Orchard Park', 'state': 'NY'},
            'Carolina Panthers': {'type': 'outdoor', 'city': 'Charlotte', 'state': 'NC'},
            'Chicago Bears': {'type': 'outdoor', 'city': 'Chicago', 'state': 'IL'},
            'Cincinnati Bengals': {'type': 'outdoor', 'city': 'Cincinnati', 'state': 'OH'},
            'Cleveland Browns': {'type': 'outdoor', 'city': 'Cleveland', 'state': 'OH'},
            'Denver Broncos': {'type': 'outdoor', 'city': 'Denver', 'state': 'CO'},
            'Green Bay Packers': {'type': 'outdoor', 'city': 'Green Bay', 'state': 'WI'},
            'Jacksonville Jaguars': {'type': 'outdoor', 'city': 'Jacksonville', 'state': 'FL'},
            'Kansas City Chiefs': {'type': 'outdoor', 'city': 'Kansas City', 'state': 'MO'},
            'Miami Dolphins': {'type': 'outdoor', 'city': 'Miami Gardens', 'state': 'FL'},
            'New England Patriots': {'type': 'outdoor', 'city': 'Foxborough', 'state': 'MA'},
            'New York Giants': {'type': 'outdoor', 'city': 'East Rutherford', 'state': 'NJ'},
            'New York Jets': {'type': 'outdoor', 'city': 'East Rutherford', 'state': 'NJ'},
            'Philadelphia Eagles': {'type': 'outdoor', 'city': 'Philadelphia', 'state': 'PA'},
            'Pittsburgh Steelers': {'type': 'outdoor', 'city': 'Pittsburgh', 'state': 'PA'},
            'San Francisco 49ers': {'type': 'outdoor', 'city': 'Santa Clara', 'state': 'CA'},
            'Seattle Seahawks': {'type': 'outdoor', 'city': 'Seattle', 'state': 'WA'},
            'Tampa Bay Buccaneers': {'type': 'outdoor', 'city': 'Tampa', 'state': 'FL'},
            'Tennessee Titans': {'type': 'outdoor', 'city': 'Nashville', 'state': 'TN'},
            'Washington Commanders': {'type': 'outdoor', 'city': 'Landover', 'state': 'MD'},
        }
    
    def get_venue_type(self, home_team: str) -> str:
        """
        Get whether game is in dome or outdoor
        
        Args:
            home_team: Home team name
        
        Returns:
            'dome' or 'outdoor'
        """
        venue = self.stadiums.get(home_team, {})
        return venue.get('type', 'outdoor')
    
    def get_weather_conditions(self, home_team: str) -> Dict:
        """
        Get weather conditions for a game
        Uses free weather API (weather.gov or similar)
        
        Args:
            home_team: Home team name
        
        Returns:
            Dict with weather info: {temp, wind_speed, conditions, precipitation}
        """
        venue_type = self.get_venue_type(home_team)
        
        # If dome, weather doesn't matter
        if venue_type == 'dome':
            return {
                'venue_type': 'dome',
                'temp': 72,
                'wind_speed': 0,
                'conditions': 'Dome (Perfect Conditions)',
                'precipitation': False,
                'impact': 'none'
            }
        
        # For outdoor games, try to get real weather
        # For now, return outdoor with unknown conditions
        # (We can add weather API integration if needed)
        
        return {
            'venue_type': 'outdoor',
            'temp': None,
            'wind_speed': None,
            'conditions': 'Outdoor',
            'precipitation': None,
            'impact': 'unknown'
        }
    
    def get_condition_adjustment(self, home_team: str, stat_type: str) -> float:
        """
        Get adjustment multiplier based on weather/venue conditions
        
        Args:
            home_team: Home team name
            stat_type: Type of stat (pass_yds, rush_yds, etc.)
        
        Returns:
            Adjustment multiplier (e.g., 0.85 for -15%, 1.05 for +5%)
        """
        conditions = self.get_weather_conditions(home_team)
        venue_type = conditions['venue_type']
        wind_speed = conditions.get('wind_speed', 0) or 0
        precipitation = conditions.get('precipitation', False)
        
        adjustment = 1.0
        factors = []
        
        # Dome benefit
        if venue_type == 'dome':
            if stat_type in ['pass_yds', 'passing_yards', 'reception_yds', 'receiving_yards']:
                adjustment *= 1.05  # +5% for passing in dome
                factors.append('Dome (+5%)')
            return adjustment, factors, 'dome'
        
        # Outdoor conditions
        # High wind impact
        if wind_speed and wind_speed >= 15:
            if stat_type in ['pass_yds', 'passing_yards', 'reception_yds', 'receiving_yards']:
                adjustment *= 0.85  # -15% for passing in wind
                factors.append(f'High Wind {wind_speed}mph (-15%)')
            elif stat_type in ['rush_yds', 'rushing_yards']:
                adjustment *= 1.10  # +10% for rushing in wind
                factors.append(f'High Wind {wind_speed}mph (+10% rush)')
        
        # Moderate wind
        elif wind_speed and 10 <= wind_speed < 15:
            if stat_type in ['pass_yds', 'passing_yards', 'reception_yds', 'receiving_yards']:
                adjustment *= 0.93  # -7% for moderate wind
                factors.append(f'Wind {wind_speed}mph (-7%)')
        
        # Precipitation (rain/snow)
        if precipitation:
            # Affects all stats negatively
            adjustment *= 0.90  # -10% for rain/snow
            factors.append('Rain/Snow (-10%)')
        
        condition_str = 'outdoor'
        if factors:
            condition_str = 'outdoor_' + '_'.join(factors)
        
        print(f"  🌦️  {home_team} venue: {venue_type}")
        if factors:
            print(f"      Adjustments: {', '.join(factors)} → {adjustment}x")
        
        return adjustment, factors, condition_str
    
    def get_game_condition_summary(self, home_team: str) -> str:
        """
        Get human-readable summary of game conditions
        
        Args:
            home_team: Home team name
        
        Returns:
            Summary string like "Dome" or "Outdoor, High Wind (15mph)"
        """
        conditions = self.get_weather_conditions(home_team)
        venue_type = conditions['venue_type']
        
        if venue_type == 'dome':
            return "🏟️ Dome (Perfect)"
        
        summary = "🌤️ Outdoor"
        
        wind = conditions.get('wind_speed')
        if wind and wind >= 15:
            summary += f", High Wind ({wind}mph)"
        elif wind and wind >= 10:
            summary += f", Windy ({wind}mph)"
        
        if conditions.get('precipitation'):
            summary += ", Rain/Snow"
        
        return summary


# ============================================================================
# TEST THE SCRAPER
# ============================================================================

if __name__ == "__main__":
    
    scraper = WeatherVenueScraper()
    
    print("="*80)
    print("🌦️  WEATHER & VENUE SCRAPER TEST")
    print("="*80)
    
    # Test some teams
    test_teams = [
        'Atlanta Falcons',  # Dome
        'Buffalo Bills',    # Outdoor (cold/wind)
        'Dallas Cowboys',   # Dome
        'Green Bay Packers', # Outdoor (cold)
    ]
    
    for team in test_teams:
        print(f"\n{team}:")
        venue_type = scraper.get_venue_type(team)
        print(f"  Venue: {venue_type}")
        
        conditions = scraper.get_weather_conditions(team)
        print(f"  Conditions: {conditions['conditions']}")
        
        # Test adjustments for passing
        adj, factors, cond = scraper.get_condition_adjustment(team, 'pass_yds')
        print(f"  Passing adjustment: {adj}x")
        if factors:
            print(f"  Factors: {', '.join(factors)}")
        
        summary = scraper.get_game_condition_summary(team)
        print(f"  Summary: {summary}")
    
    print("\n" + "="*80)
    print("✅ Test complete!")
    print("="*80)
