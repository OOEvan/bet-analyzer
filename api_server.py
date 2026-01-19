"""
Flask API for Automated Bet Finder
Connects the automated scraper to the HTML interface
FIXED: Updated to work with new OddsScraper structure
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from automated_bet_finder import AutomatedBetFinder
from defense_stats_scraper import DefenseStatsScraper
from weather_venue_scraper import WeatherVenueScraper
import json

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Initialize the bet finder
# TODO: Replace with your actual API key
API_KEY = "6ae9b6fd8e38e1c74d1b93cc0b22b867"
finder = AutomatedBetFinder(API_KEY)

# Initialize defense stats scraper
defense_scraper = DefenseStatsScraper()

# Initialize weather/venue scraper
weather_scraper = WeatherVenueScraper()


@app.route('/api/scan-best-bets', methods=['POST'])
def scan_best_bets():
    """
    Scan for best bets automatically
    Body: {
        "players": [
            {"name": "Lamar Jackson", "props": ["player_pass_yds", "player_pass_tds"]},
            ...
        ],
        "min_edge": 3.0
    }
    """
    try:
        data = request.json
        players = data.get('players', [])
        min_edge = data.get('min_edge', 3.0)
        
        # Find best bets
        best_bets = finder.find_best_bets(players, min_edge=min_edge)
        
        return jsonify({
            'success': True,
            'bets': best_bets,
            'count': len(best_bets)
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/quick-scan', methods=['GET'])
def quick_scan():
    """
    Quick scan - automatically finds ALL players with props in today's games
    """
    try:
        print("\n" + "="*80)
        print("🚀 QUICK SCAN - Finding all available props for today's games")
        print("="*80)
        
        # Get all player props from today's games
        all_props = finder.odds_scraper.get_all_player_props()
        
        if not all_props:
            return jsonify({
                'success': False,
                'error': 'No games or props found for today'
            }), 404
        
        # Extract all unique players across all games and markets
        all_players = []
        players_seen = set()
        
        for event_id, event_data in all_props.items():
            print(f"\n📊 Scanning: {event_data['event_name']}")
            
            for prop_type, prop_data in event_data['props'].items():
                if not prop_data or 'bookmakers' not in prop_data:
                    continue
                
                # Extract players from this market
                for bookmaker in prop_data['bookmakers']:
                    for market in bookmaker.get('markets', []):
                        for outcome in market.get('outcomes', []):
                            player_name = outcome.get('description', '')
                            
                            if player_name and player_name not in players_seen:
                                players_seen.add(player_name)
                                
                                # Add player with this prop type
                                # Check if player already in list
                                player_entry = next((p for p in all_players if p['name'] == player_name), None)
                                
                                if player_entry:
                                    # Add this prop type if not already there
                                    if prop_type not in player_entry['props']:
                                        player_entry['props'].append(prop_type)
                                else:
                                    # New player
                                    all_players.append({
                                        'name': player_name,
                                        'props': [prop_type]
                                    })
        
        print(f"\n✅ Found {len(all_players)} unique players with props")
        
        # Now analyze all these players
        best_bets = finder.find_best_bets(all_players, min_edge=3.0)
        
        return jsonify({
            'success': True,
            'bets': best_bets[:20],  # Top 20 best bets
            'total_analyzed': len(all_players)
        })
    
    except Exception as e:
        print(f"❌ Quick scan error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/build-parlay', methods=['POST'])
def build_parlay():
    """
    Build optimal parlay from best bets
    Body: {
        "bets": [...],  // Array of bet objects
        "num_legs": 3,
        "risk_level": "conservative"  // or "balanced" or "aggressive"
    }
    """
    try:
        data = request.json
        bets = data.get('bets', [])
        num_legs = data.get('num_legs', 3)
        risk_level = data.get('risk_level', 'conservative')
        
        parlay = finder.build_optimal_parlay(bets, num_legs=num_legs, risk_level=risk_level)
        
        return jsonify({
            'success': True,
            'parlay': parlay
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/get-player-stats', methods=['POST'])
def get_player_stats():
    """
    Get recent stats for a specific player
    Body: {
        "player_name": "Lamar Jackson",
        "stat_type": "pass_yds",
        "num_games": 7
    }
    """
    try:
        data = request.json
        player_name = data.get('player_name')
        stat_type = data.get('stat_type')
        num_games = data.get('num_games', 7)
        
        stats = finder.stats_scraper.get_player_recent_games(
            player_name, 
            stat_type, 
            num_games
        )
        
        return jsonify({
            'success': True,
            'player': player_name,
            'stat_type': stat_type,
            'games': stats,
            'average': sum(stats) / len(stats) if stats else 0
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/get-live-props', methods=['GET'])
def get_live_props():
    """
    Get all available live props for today's games
    """
    try:
        all_props = finder.odds_scraper.get_all_player_props()
        
        # Format for easier reading
        formatted_props = {}
        for event_id, event_data in all_props.items():
            formatted_props[event_data['event_name']] = {
                'commence_time': event_data['commence_time'],
                'available_markets': list(event_data['props'].keys()),
                'player_count': sum(
                    finder.odds_scraper._count_players_in_market(prop_data) 
                    for prop_data in event_data['props'].values()
                )
            }
        
        return jsonify({
            'success': True,
            'games': formatted_props,
            'total_games': len(formatted_props)
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/get-game-players', methods=['POST'])
def get_game_players():
    """
    Get players available for a specific game by extracting from live odds
    Body: {
        "team1": "Colts",
        "team2": "49ers"
    }
    """
    try:
        data = request.json
        team1 = data.get('team1', '').lower()
        team2 = data.get('team2', '').lower()
        
        # Get all live props
        all_props = finder.odds_scraper.get_all_player_props()
        
        # Find the matching game and extract player names
        game_players = []
        
        for event_id, event_data in all_props.items():
            event_name = event_data['event_name'].lower()
            home_team = event_data['home_team'].lower()
            away_team = event_data['away_team'].lower()
            
            # Check if this is the game we're looking for
            if (team1 in event_name or team1 in home_team or team1 in away_team) and \
               (team2 in event_name or team2 in home_team or team2 in away_team):
                
                # Extract all players from this game's props
                players_found = set()
                
                for prop_type, prop_data in event_data['props'].items():
                    if prop_data and 'bookmakers' in prop_data:
                        for bookmaker in prop_data['bookmakers']:
                            for market in bookmaker.get('markets', []):
                                for outcome in market.get('outcomes', []):
                                    player_name = outcome.get('description', '')
                                    if player_name:
                                        players_found.add(player_name)
                
                # Convert to list with all prop types
                all_prop_types = ['player_pass_yds', 'player_pass_tds', 'player_rush_yds', 
                                  'player_rush_tds', 'player_receptions', 'player_reception_yds',
                                  'player_rec_tds']
                
                game_players = [
                    {'name': player, 'props': all_prop_types} 
                    for player in sorted(players_found)
                ]
                
                return jsonify({
                    'success': True,
                    'game': event_data['event_name'],
                    'players': game_players,
                    'total_players': len(game_players)
                })
        
        return jsonify({
            'success': False,
            'error': f'No game found matching {team1} vs {team2}'
        }), 404
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500




@app.route('/api/get-matchup-adjustment', methods=['POST'])
def get_matchup_adjustment():
    """
    Get defensive matchup adjustment for a player
    Body: {
        "opponent": "PHI",
        "stat_type": "pass_yds"
    }
    """
    try:
        data = request.json
        opponent = data.get('opponent', '')
        stat_type = data.get('stat_type', '')
        
        if not opponent or not stat_type:
            return jsonify({
                'success': False,
                'error': 'Missing opponent or stat_type'
            }), 400
        
        adjustment = defense_scraper.get_matchup_adjustment(opponent, stat_type)
        
        return jsonify({
            'success': True,
            'opponent': opponent.upper(),
            'stat_type': stat_type,
            'adjustment': adjustment
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500




@app.route('/api/get-condition-adjustment', methods=['POST'])
def get_condition_adjustment():
    """
    Get weather/venue adjustment for a game
    Body: {
        "home_team": "Atlanta Falcons",
        "stat_type": "pass_yds"
    }
    """
    try:
        data = request.json
        home_team = data.get('home_team', '')
        stat_type = data.get('stat_type', '')
        
        if not home_team or not stat_type:
            return jsonify({
                'success': False,
                'error': 'Missing home_team or stat_type'
            }), 400
        
        adjustment, factors, condition = weather_scraper.get_condition_adjustment(home_team, stat_type)
        summary = weather_scraper.get_game_condition_summary(home_team)
        
        return jsonify({
            'success': True,
            'home_team': home_team,
            'stat_type': stat_type,
            'adjustment': adjustment,
            'factors': factors,
            'condition': condition,
            'summary': summary
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Automated Bet Finder API',
        'version': '2.0 - Fixed Event Endpoint'
    })


if __name__ == '__main__':
    print("=" * 80)
    print("🚀 Starting Automated Bet Finder API v2.0")
    print("=" * 80)
    print("\nAPI Endpoints:")
    print("  POST /api/scan-best-bets    - Scan for best bets (custom players)")
    print("  GET  /api/quick-scan        - Quick scan of popular players")
    print("  POST /api/build-parlay      - Build optimal parlay")
    print("  POST /api/get-player-stats  - Get player statistics")
    print("  GET  /api/get-live-props    - Get all available live props")
    print("  GET  /api/health            - Health check")
    print("\n" + "=" * 80)
    print("\n⚠️  IMPORTANT: Make sure your API key is set in this file!")
    print("=" * 80)
    
    app.run(debug=True, host='0.0.0.0', port=5002)
