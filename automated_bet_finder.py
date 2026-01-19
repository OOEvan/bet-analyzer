"""
Advanced NFL Bet Finder - Automated Stats & Odds Scraper
Automatically finds the best betting opportunities by:
1. Scraping player stats from NFL.com
2. Pulling live odds from The Odds API (FanDuel, DraftKings, etc.)
3. Calculating projections and finding edges
4. Ranking best bets by expected value

FIXED: Now uses correct /events/{event_id}/odds endpoint for player props
"""

import requests
from bs4 import BeautifulSoup
import json
import statistics
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import time
import sqlite3
from pfr_stats_scraper import PFRStatsScraper
import os
import sys

# Import enhanced bet analysis
try:
    from enhanced_bet_analysis import EnhancedBetAnalyzer
    ENHANCED_ANALYSIS_AVAILABLE = True
except ImportError:
    print("⚠️  Enhanced bet analysis not available")
    ENHANCED_ANALYSIS_AVAILABLE = False


# ============================================================================
# NFL STATS SCRAPER - USING PRO FOOTBALL REFERENCE WITH RATE LIMITING
# ============================================================================

# We use PFRStatsScraper with delays to avoid rate limiting
NFLStatsScraper = PFRStatsScraper


# ============================================================================
# ODDS SCRAPER (The Odds API)
# ============================================================================

class OddsScraper:
    """Fetch live betting odds from The Odds API"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.the-odds-api.com/v4"
    
    def get_all_events(self, sport: str = 'americanfootball_nfl') -> List[Dict]:
        """Get all upcoming events/games"""
        endpoint = f"{self.base_url}/sports/{sport}/events"
        
        params = {'apiKey': self.api_key}
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            events = response.json()
            print(f"✅ Found {len(events)} upcoming games")
            return events
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching events: {e}")
            return []
    
    def get_all_player_props(self, sport: str = 'americanfootball_nfl') -> Dict:
        """
        Fetch all player prop markets from multiple sportsbooks
        Returns organized data by event and market
        """
        # First get all events
        events = self.get_all_events(sport)
        
        if not events:
            print("No events found")
            return {}
        
        markets = [
            'player_pass_yds',
            'player_pass_tds', 
            'player_rush_yds',
            'player_rush_tds',
            'player_receptions',
            'player_reception_yds',
            'player_anytime_td'
        ]
        
        all_props = {}
        
        # Fetch props for each event (limit to first 3 games to save API calls)
        for event in events[:3]:
            event_id = event['id']
            event_name = f"{event['home_team']} vs {event['away_team']}"
            print(f"\n📊 Fetching props for: {event_name}")
            
            event_props = {}
            
            for market in markets:
                props = self._fetch_event_market(sport, event_id, market)
                if props:
                    event_props[market] = props
                    # Count how many players have odds in this market
                    player_count = self._count_players_in_market(props)
                    print(f"  ✓ {market}: {player_count} players")
                time.sleep(0.5)  # Rate limiting
            
            all_props[event_id] = {
                'event_name': event_name,
                'home_team': event['home_team'],
                'away_team': event['away_team'],
                'commence_time': event['commence_time'],
                'props': event_props
            }
        
        return all_props
    
    def _fetch_event_market(self, sport: str, event_id: str, market: str) -> Optional[Dict]:
        """Fetch a specific market for a specific event"""
        endpoint = f"{self.base_url}/sports/{sport}/events/{event_id}/odds"
        
        params = {
            'apiKey': self.api_key,
            'regions': 'us',
            'markets': market,
            'oddsFormat': 'american',
            'bookmakers': 'fanduel'  # Only FanDuel
        }
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"    ⚠️  Error fetching {market}: {str(e)[:100]}")
            return None
    
    def _count_players_in_market(self, market_data: Dict) -> int:
        """Count unique players in a market"""
        players = set()
        
        if not market_data or 'bookmakers' not in market_data:
            return 0
        
        for bookmaker in market_data.get('bookmakers', []):
            for market in bookmaker.get('markets', []):
                for outcome in market.get('outcomes', []):
                    player_name = outcome.get('description', '')
                    if player_name:
                        players.add(player_name)
        
        return len(players)
    
    def get_best_lines(self, player_name: str, prop_type: str, all_props: Dict) -> Optional[Dict]:
        """
        Find the best available lines for a player across all sportsbooks
        """
        best_over = None
        best_under = None
        
        # Search through all events
        for event_id, event_data in all_props.items():
            if prop_type not in event_data['props']:
                continue
            
            market_data = event_data['props'][prop_type]
            
            if not market_data or 'bookmakers' not in market_data:
                continue
            
            for bookmaker in market_data.get('bookmakers', []):
                for market in bookmaker.get('markets', []):
                    for outcome in market.get('outcomes', []):
                        outcome_player = outcome.get('description', '').lower()
                        
                        if player_name.lower() not in outcome_player:
                            continue
                        
                        point = outcome.get('point')
                        price = outcome.get('price')
                        outcome_name = outcome.get('name')
                        
                        if outcome_name == 'Over':
                            if not best_over or point < best_over['point']:
                                best_over = {
                                    'point': point,
                                    'price': price,
                                    'bookmaker': bookmaker['title']
                                }
                        
                        elif outcome_name == 'Under':
                            if not best_under or point > best_under['point']:
                                best_under = {
                                    'point': point,
                                    'price': price,
                                    'bookmaker': bookmaker['title']
                                }
        
        if best_over and best_under:
            return {
                'player': player_name,
                'prop_type': prop_type,
                'best_over': best_over,
                'best_under': best_under
            }
        
        return None


# ============================================================================
# AUTOMATED BET FINDER
# ============================================================================

class AutomatedBetFinder:
    """
    Main class that combines stats scraping, odds scraping, and edge finding
    """
    
    def __init__(self, odds_api_key: str, db_path: str = 'nfl_props.db'):
        self.stats_scraper = NFLStatsScraper()
        self.odds_scraper = OddsScraper(odds_api_key)
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize database for caching"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS best_bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def calculate_projection(self, game_history: List[float], sportsbook_line: float, 
                           player_name: str = None, prop_type: str = None, odds: int = None) -> Dict:
        """Calculate projection from game history with reliability scoring"""
        if not game_history:
            return None
        
        # Weighted average (recent games weighted more)
        weights = list(range(1, len(game_history) + 1))
        weighted_avg = sum(g * w for g, w in zip(game_history, weights)) / sum(weights)
        
        # Hit rate
        hits_over = sum(1 for g in game_history if g > sportsbook_line)
        hit_rate = (hits_over / len(game_history)) * 100
        
        # Edge calculation
        edge = weighted_avg - sportsbook_line
        edge_percent = (edge / sportsbook_line) * 100 if sportsbook_line != 0 else 0
        
        # Recommendation
        if abs(edge_percent) < 3 or (45 < hit_rate < 55):
            recommendation = 'PASS'
            confidence = 'Low'
        elif edge > 0 and edge_percent >= 8 and hit_rate >= 55:
            recommendation = 'OVER'
            confidence = 'High'
        elif edge > 0 and edge_percent >= 3:
            recommendation = 'OVER'
            confidence = 'Medium'
        elif edge < 0 and edge_percent <= -8 and hit_rate <= 45:
            recommendation = 'UNDER'
            confidence = 'High'
        elif edge < 0 and edge_percent <= -3:
            recommendation = 'UNDER'
            confidence = 'Medium'
        else:
            recommendation = 'PASS'
            confidence = 'Low'
        
        result = {
            'weighted_avg': round(weighted_avg, 1),
            'hit_rate': round(hit_rate, 1),
            'edge': round(edge, 1),
            'edge_percent': round(edge_percent, 1),
            'recommendation': recommendation,
            'confidence': confidence,
            'games': game_history  # Include games for reliability calculation
        }
        
        # Calculate reliability if enhanced analysis is available
        if ENHANCED_ANALYSIS_AVAILABLE and player_name and prop_type and odds:
            try:
                reliability = EnhancedBetAnalyzer.calculate_reliability_score(
                    player_name=player_name,
                    prop_type=prop_type,
                    recent_games=game_history,
                    line=sportsbook_line,
                    edge_percent=edge_percent
                )
                result['reliability'] = reliability
            except Exception as e:
                print(f"  ⚠️  Could not calculate reliability: {e}")
        
        return result
    
    
    def _filter_low_usage_players(self, players: List[Dict]) -> List[Dict]:
        """
        Filter out low-usage players (backups, low-snap TEs, committee RBs)
        """
        # Known backup QBs, TEs, and low-usage players to exclude
        backup_players = {
            # Backup QBs
            'malik willis', 'sam darnold', 'taylor heinicke', 'mason rudolph',
            'mitchell trubisky', 'josh dobbs', 'jacoby brissett', 'andy dalton',
            'jameis winston', 'drew lock', 'trevor siemian', 'jimmy garoppolo',
            
            # Backup TEs (low snap count)
            'davis allen', 'foster moreau', 'johnny mundt', 'nick vannett',
            'john bates', 'tre\' mckitty', 'jordan akins', 'mo alie-cox',
            'tommy tremble', 'charlie kolar', 'will dissly', 'gerald everett',
            'zach gentry', 'hunter henry', 'josh oliver', 'luke farrell',
            
            # Committee/Backup RBs (RB2/RB3)
            'blake corum', 'royce freeman', 'ty johnson', 'pierre strong',
            'clyde edwards-helaire', 'elijah mitchell', 'cam akers', 'ronnie rivers',
            'jashaun corbin', 'malik davis', 'snoop conner', 'patrick taylor',
            'hassan haskins', 'deon jackson', 'julius chestnut', 'trayveon williams',
            
            # WR3/WR4 (inconsistent targets)
            'tutu atwell', 'demarcus robinson', 'tyler boyd', 'van jefferson',
            'kalif raymond', 'craig reynolds', 'robbie chosen', 'james proche',
            'tyler johnson', 'jalen nailor', 'trent sherfield', 'kj osborn',
        }
        
        # RB committees - keep only the primary back
        rb_committees = {
            'rams': {'primary': ['kyren williams'], 'exclude': ['blake corum', 'royce freeman']},
            'chiefs': {'primary': ['isiah pacheco'], 'exclude': ['clyde edwards-helaire']},
            '49ers': {'primary': ['christian mccaffrey', 'jordan mason'], 'exclude': ['elijah mitchell']},
            'dolphins': {'primary': ['de\'von achane', 'raheem mostert'], 'exclude': ['jeff wilson']},
        }
        
        filtered = []
        
        for player_info in players:
            player_name = player_info['name'].lower()
            
            # Check if player is in backup list
            if player_name in backup_players:
                print(f"  ⚠️  Filtered out: {player_info['name']} (backup/low usage)")
                continue
            
            # Additional filters based on prop types
            props = player_info.get('props', [])
            
            # If a TE only has reception props but not many, likely backup
            if any('reception' in p for p in props):
                # Check if it's a rarely-targeted player
                if any(backup in player_name for backup in ['allen', 'bates', 'moreau', 'mundt']):
                    print(f"  ⚠️  Filtered out: {player_info['name']} (low-target TE)")
                    continue
            
            # Passed all filters
            filtered.append(player_info)
        
        return filtered
    
    def find_best_bets(self, players: List[Dict], min_edge: float = 5.0) -> List[Dict]:
        """
        Find the best betting opportunities across all players
        """
        print("\n" + "="*80)
        print("🔍 SCANNING FOR BEST BETS")
        print("="*80)
        
        # Get all odds data
        print("\n📡 Fetching live odds from sportsbooks...")
        all_props = self.odds_scraper.get_all_player_props()
        
        if not all_props:
            print("❌ No props data available")
            return []
        
        # Filter out low-usage players before analysis
        print("\n🔧 Filtering players by usage/role...")
        filtered_players = self._filter_low_usage_players(players)
        print(f"  ✅ {len(filtered_players)} of {len(players)} players passed usage filter")
        
        best_bets = []
        
        print("\n" + "="*80)
        print("🎯 ANALYZING PLAYER PROPS")
        print("="*80)
        
        for player_info in filtered_players:
            player_name = player_info['name']
            prop_types = player_info['props']
            
            print(f"\n👤 {player_name}")
            
            for prop_type in prop_types:
                # Get best lines from odds
                lines = self.odds_scraper.get_best_lines(player_name, prop_type, all_props)
                
                if not lines:
                    print(f"  ⚠️  No odds for {prop_type}")
                    continue
                
                # Get stats history (with delay to avoid rate limiting)
                stat_type = prop_type.replace('player_', '')
                game_history = self.stats_scraper.get_player_recent_games(
                    player_name, 
                    stat_type,
                    num_games=7
                )
                
                # Add 2-second delay after each stat fetch to avoid PFR rate limiting
                time.sleep(2)
                
                # Analyze over bet
                over_line = lines['best_over']['point']
                over_odds = lines['best_over']['price']
                over_bookmaker = lines['best_over']['bookmaker']
                
                over_projection = self.calculate_projection(
                    game_history, 
                    over_line,
                    player_name=player_name,
                    prop_type=prop_type,
                    odds=over_odds
                )
                
                if over_projection and abs(over_projection['edge_percent']) >= min_edge:
                    if over_projection['recommendation'] == 'OVER':
                        bet = {
                            'player': player_name,
                            'prop_type': prop_type,
                            'bet': 'OVER',
                            'line': over_line,
                            'odds': over_odds,
                            'bookmaker': over_bookmaker,
                            **over_projection
                        }
                        best_bets.append(bet)
                        
                        # Show reliability in output if available
                        reliability_str = ""
                        if 'reliability' in over_projection:
                            rel_score = over_projection['reliability']['reliability_score']
                            reliability_str = f" | Reliability: {rel_score}/100"
                        
                        print(f"  ✅ OVER {over_line} ({over_odds}) - Edge: {over_projection['edge_percent']:+.1f}%{reliability_str}")
                
                # Analyze under bet
                under_line = lines['best_under']['point']
                under_odds = lines['best_under']['price']
                under_bookmaker = lines['best_under']['bookmaker']
                
                under_projection = self.calculate_projection(
                    game_history, 
                    under_line,
                    player_name=player_name,
                    prop_type=prop_type,
                    odds=under_odds
                )
                
                if under_projection and abs(under_projection['edge_percent']) >= min_edge:
                    if under_projection['recommendation'] == 'UNDER':
                        bet = {
                            'player': player_name,
                            'prop_type': prop_type,
                            'bet': 'UNDER',
                            'line': under_line,
                            'odds': under_odds,
                            'bookmaker': under_bookmaker,
                            **under_projection
                        }
                        best_bets.append(bet)
                        
                        # Show reliability in output if available
                        reliability_str = ""
                        if 'reliability' in under_projection:
                            rel_score = under_projection['reliability']['reliability_score']
                            reliability_str = f" | Reliability: {rel_score}/100"
                        
                        print(f"  ✅ UNDER {under_line} ({under_odds}) - Edge: {under_projection['edge_percent']:+.1f}%{reliability_str}")
        
        # Sort by edge percentage
        best_bets.sort(key=lambda x: abs(x['edge_percent']), reverse=True)
        
        # Save to database
        if best_bets:
            self._save_best_bets(best_bets)
        
        print("\n" + "="*80)
        print(f"✅ Found {len(best_bets)} bets with {min_edge}%+ edge")
        print("="*80)
        
        return best_bets
    
    def _save_best_bets(self, bets: List[Dict]):
        """Save best bets to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for bet in bets:
            cursor.execute('''
                INSERT INTO best_bets 
                (player_name, prop_type, line, projection, edge, edge_percent,
                 hit_rate, recommendation, confidence, bookmaker, odds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                bet['player'],
                bet['prop_type'],
                bet['line'],
                bet['weighted_avg'],
                bet['edge'],
                bet['edge_percent'],
                bet['hit_rate'],
                bet['bet'],
                bet['confidence'],
                bet['bookmaker'],
                bet['odds']
            ))
        
        conn.commit()
        conn.close()
    
    def print_best_bets(self, bets: List[Dict], top_n: int = 10):
        """Print the top N best bets in a nice format"""
        print("\n" + "="*80)
        print(f"🔥 TOP {min(top_n, len(bets))} BEST BETS (Sorted by Edge)")
        print("="*80)
        
        for i, bet in enumerate(bets[:top_n], 1):
            confidence_emoji = '🔥' if bet['confidence'] == 'High' else '⚡'
            
            print(f"\n{i}. {confidence_emoji} {bet['player']} - {bet['prop_type'].replace('player_', '').upper()}")
            print(f"   Bet: {bet['bet']} {bet['line']}")
            print(f"   Projection: {bet['weighted_avg']} | Hit Rate: {bet['hit_rate']}%")
            print(f"   Edge: {bet['edge']:+.1f} ({bet['edge_percent']:+.1f}%)")
            print(f"   Odds: {bet['odds']:+d} at {bet['bookmaker']}")
            print(f"   Confidence: {bet['confidence']}")
        
        print("\n" + "="*80)
    
    def build_optimal_parlay(self, bets: List[Dict], num_legs: int = 3, risk_level: str = 'conservative') -> Dict:
        """
        Build an optimal parlay from best bets with proper filtering
        
        Args:
            bets: List of bet dictionaries
            num_legs: Number of legs in parlay (default 3)
            risk_level: 'conservative', 'balanced', or 'aggressive'
        
        Returns:
            Dictionary with parlay details and recommendation
        """
        # Define backup players to filter out
        BACKUP_RBS = {
            'keaton mitchell', 'kenneth gainwell', 'pierre strong', 'ty johnson',
            'blake corum', 'royce freeman', 'clyde edwards-helaire', 'elijah mitchell',
            'cam akers', 'ronnie rivers', 'jashaun corbin', 'malik davis',
            'brian robinson jr', 'jordan mason', 'rico dowdle', 'tyjae spears'
        }
        
        BACKUP_TES = {
            'aj barner', 'foster moreau', 'tommy tremble', 'charlie kolar',
            'will dissly', 'gerald everett', 'zach gentry', 'josh oliver',
            'johnny mundt', 'nick vannett', 'john bates', 'jordan akins'
        }
        
        # Filter and score bets based on risk level
        scored_bets = []
        
        for bet in bets:
            player_lower = bet['player'].lower()
            
            # Calculate true edge (hit rate vs implied probability)
            hit_rate = bet.get('hit_rate', 50)
            odds = bet['odds']
            
            if odds < 0:
                implied_prob = (abs(odds) / (abs(odds) + 100)) * 100
            else:
                implied_prob = (100 / (odds + 100)) * 100
            
            true_edge = hit_rate - implied_prob
            
            # Get reliability if available
            reliability_score = 50  # default
            consistency_score = 50  # default
            cv = 50  # default
            
            if 'reliability' in bet:
                reliability_score = bet['reliability'].get('reliability_score', 50)
                if 'consistency' in bet['reliability']:
                    consistency_score = bet['reliability']['consistency'].get('consistency_score', 50)
                    cv = bet['reliability']['consistency'].get('coefficient_variation', 50)
            
            # Check if backup player
            is_backup = player_lower in BACKUP_RBS or player_lower in BACKUP_TES
            
            # Check prop type for volatility (receiving yards for RBs is volatile)
            prop_type = bet.get('prop_type', '')
            is_volatile_prop = (
                ('rush_yds' in prop_type or 'reception_yds' in prop_type) and
                cv > 40
            ) or (
                'reception_yds' in prop_type and 'rb' in bet.get('position', '').lower()
            )
            
            # Apply filters based on risk level
            if risk_level == 'conservative':
                # Conservative: High reliability, no backups, low volatility
                if is_backup:
                    continue  # Skip backups entirely
                if reliability_score < 70:
                    continue  # Need high reliability
                if cv > 25:
                    continue  # Too volatile
                if true_edge < 5:
                    continue  # Need decent edge
                if hit_rate < 60:
                    continue  # Need high hit rate
                    
            elif risk_level == 'balanced':
                # Balanced: Medium reliability, max one backup, medium volatility
                if reliability_score < 55:
                    continue
                if true_edge < 3:
                    continue
                if hit_rate < 50:
                    continue
                    
            # For aggressive, take all bets with positive edge
            elif risk_level == 'aggressive':
                if true_edge < 1:
                    continue
            
            # Calculate composite score for ranking
            # Prioritize: true edge, reliability, hit rate
            composite_score = (
                true_edge * 2.0 +  # True edge is most important
                (reliability_score / 10) +
                (hit_rate / 10) +
                (-10 if is_backup else 0) +  # Penalty for backups
                (-5 if is_volatile_prop else 0)  # Penalty for volatile props
            )
            
            scored_bets.append({
                **bet,
                'true_edge': true_edge,
                'reliability_score': reliability_score,
                'consistency_score': consistency_score,
                'cv': cv,
                'is_backup': is_backup,
                'is_volatile': is_volatile_prop,
                'composite_score': composite_score
            })
        
        # Sort by composite score
        scored_bets.sort(key=lambda x: x['composite_score'], reverse=True)
        
        # For conservative, limit to one backup max
        if risk_level == 'balanced':
            backup_count = 0
            filtered_bets = []
            for bet in scored_bets:
                if bet['is_backup']:
                    if backup_count < 1:  # Max 1 backup
                        filtered_bets.append(bet)
                        backup_count += 1
                else:
                    filtered_bets.append(bet)
            scored_bets = filtered_bets
        
        # Take top N legs
        if len(scored_bets) < num_legs:
            return {
                'error': f'Not enough qualifying bets for {risk_level} parlay',
                'found': len(scored_bets),
                'needed': num_legs,
                'suggestion': 'Try "balanced" or "aggressive" risk level'
            }
        
        parlay_legs = scored_bets[:num_legs]
        
        # Calculate parlay odds and probabilities
        combined_decimal = 1
        combined_prob = 1
        total_true_edge = 0
        
        for leg in parlay_legs:
            # Convert American to decimal
            odds = leg['odds']
            if odds > 0:
                decimal = (odds / 100) + 1
            else:
                decimal = (100 / abs(odds)) + 1
            
            combined_decimal *= decimal
            
            # Use hit rate for probability
            prob = leg['hit_rate'] / 100
            combined_prob *= prob
            
            # Sum true edges
            total_true_edge += leg['true_edge']
        
        avg_true_edge = total_true_edge / len(parlay_legs)
        
        # Convert to American odds
        if combined_decimal >= 2:
            american_odds = int((combined_decimal - 1) * 100)
        else:
            american_odds = int(-100 / (combined_decimal - 1))
        
        # Calculate parlay true edge
        parlay_implied_prob = implied_prob = (abs(american_odds) / (abs(american_odds) + 100)) * 100 if american_odds < 0 else (100 / (american_odds + 100)) * 100
        parlay_true_edge = (combined_prob * 100) - parlay_implied_prob
        
        payout = combined_decimal * 100
        profit = payout - 100
        
        # Determine if it's actually conservative based on win rate
        actual_win_rate = combined_prob * 100
        if actual_win_rate >= 60:
            actual_risk = 'Conservative'
        elif actual_win_rate >= 40:
            actual_risk = 'Balanced'
        else:
            actual_risk = 'Aggressive'
        
        # Build recommendation
        if parlay_true_edge < 0:
            recommendation = 'AVOID'
            reason = 'Negative parlay edge'
        elif avg_true_edge < 3:
            recommendation = 'PASS'
            reason = 'Low average true edge per leg'
        elif parlay_true_edge >= 10 and avg_true_edge >= 8:
            recommendation = 'STRONG PLAY'
            reason = 'Excellent true edge on all legs'
        elif parlay_true_edge >= 5 and avg_true_edge >= 5:
            recommendation = 'GOOD VALUE'
            reason = 'Solid true edge across legs'
        else:
            recommendation = 'FAIR'
            reason = 'Positive but thin edge'
        
        return {
            'legs': parlay_legs,
            'num_legs': len(parlay_legs),
            'combined_odds': f"+{american_odds}" if american_odds > 0 else str(american_odds),
            'combined_probability': round(combined_prob * 100, 1),
            'avg_true_edge': round(avg_true_edge, 1),
            'parlay_true_edge': round(parlay_true_edge, 1),
            'avg_hit_rate': round(sum(leg['hit_rate'] for leg in parlay_legs) / len(parlay_legs), 1),
            'payout_on_100': round(profit, 0),
            'total_payout': round(payout, 0),
            'requested_risk': risk_level.title(),
            'actual_risk': actual_risk,
            'recommendation': recommendation,
            'reason': reason,
            'warnings': [
                f"⚠️ Includes backup: {leg['player']}" for leg in parlay_legs if leg.get('is_backup')
            ] + [
                f"⚠️ Volatile prop: {leg['player']} {leg['prop_type']}" for leg in parlay_legs if leg.get('is_volatile')
            ]
        }


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    
    # Initialize with your API key
    API_KEY = "your_api_key_here"  # Replace with your actual key
    
    finder = AutomatedBetFinder(API_KEY)
    
    # Active players for Week 16
    players_to_analyze = [
        {'name': 'Lamar Jackson', 'props': ['player_pass_yds', 'player_pass_tds']},
        {'name': 'Baker Mayfield', 'props': ['player_pass_yds', 'player_pass_tds']},
        {'name': 'Brock Purdy', 'props': ['player_pass_yds', 'player_pass_tds']},
        {'name': 'Saquon Barkley', 'props': ['player_rush_yds', 'player_rush_tds']},
        {'name': 'Derrick Henry', 'props': ['player_rush_yds', 'player_rush_tds']},
        {'name': 'CeeDee Lamb', 'props': ['player_reception_yds', 'player_receptions']},
        {'name': 'Ja''Marr Chase', 'props': ['player_reception_yds', 'player_receptions']},
    ]
    
    # Find the best bets
    best_bets = finder.find_best_bets(players_to_analyze, min_edge=3.0)
    
    # Display results
    if best_bets:
        finder.print_best_bets(best_bets, top_n=10)
        
        # Build optimal parlay
        print("\n" + "="*80)
        print("🎯 OPTIMAL PARLAY SUGGESTION")
        print("="*80)
        
        parlay = finder.build_optimal_parlay(best_bets, num_legs=3)
        
        if 'error' not in parlay:
            print(f"\n{parlay['num_legs']}-Leg Parlay:")
            for i, leg in enumerate(parlay['legs'], 1):
                print(f"  {i}. {leg['player']} - {leg['bet']} {leg['line']} ({leg['odds']:+d})")
            
            print(f"\nCombined Odds: {parlay['combined_odds']}")
            print(f"Combined Probability: {parlay['combined_probability']}%")
            print(f"Bet $100 to win: ${parlay['payout_on_100']}")
            print(f"Total payout: ${parlay['total_payout']}")
    else:
        print("\n❌ No bets found with sufficient edge")
    
    print("\n" + "="*80)
