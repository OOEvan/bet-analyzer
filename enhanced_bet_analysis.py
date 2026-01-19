"""
Enhanced Bet Analysis Module
Adds consistency filtering, reliability scoring, and game script adjustments
"""

import statistics
from typing import List, Dict, Optional, Tuple


class EnhancedBetAnalyzer:
    """Enhanced analysis with consistency metrics and reliability scoring"""
    
    # Known backup RBs and their primary backs
    BACKUP_RBS = {
        # 49ers
        'brian robinson jr': 'christian mccaffrey',
        'jordan mason': 'christian mccaffrey',
        
        # Cowboys
        'rico dowdle': 'tony pollard',
        
        # Eagles
        'kenny gainwell': "d'andre swift",
        
        # Chiefs
        'clyde edwards-helaire': 'isiah pacheco',
        
        # Bengals
        'chase brown': 'joe mixon',
        
        # Add more as needed
    }
    
    # Committee backfields (multiple RBs share carries)
    COMMITTEE_BACKFIELDS = {
        'rams': ['kyren williams', 'royce freeman'],
        'patriots': ['rhamondre stevenson', 'ezekiel elliott'],
        'browns': ['jerome ford', 'kareem hunt'],
    }
    
    # Backup/Low-usage TEs
    BACKUP_TES = {
        'aj barner',  # backup to noah fant
        'foster moreau',
        'johnny mundt',
        'davis allen',
        'john bates',
        'tommy tremble',
        'charlie kolar',
        'harrison bryant',
    }
    
    @staticmethod
    def calculate_consistency_score(recent_games: List[float], line: float) -> Dict:
        """
        Calculate consistency metrics for a bet
        Returns consistency score, std dev, hit rate, and variance
        """
        if not recent_games or len(recent_games) < 3:
            return {
                'consistency_score': 0,
                'std_dev': None,
                'variance': None,
                'hit_rate': 0,
                'reliability': 'Unknown'
            }
        
        mean_val = statistics.mean(recent_games)
        std_dev = statistics.stdev(recent_games) if len(recent_games) > 1 else 0
        
        # Calculate coefficient of variation (std dev as % of mean)
        cv = (std_dev / mean_val * 100) if mean_val > 0 else 999
        
        # Hit rate (% of games that hit the over)
        hits_over = sum(1 for g in recent_games if g > line)
        hit_rate = (hits_over / len(recent_games)) * 100
        
        # Consistency score (0-100, higher is better)
        # Based on low variance + high hit rate
        if cv < 15:
            consistency_score = 90 + min(10, hit_rate - 80)
        elif cv < 25:
            consistency_score = 75 + min(15, (hit_rate - 70) / 2)
        elif cv < 40:
            consistency_score = 60 + min(15, (hit_rate - 60) / 2)
        elif cv < 60:
            consistency_score = 40 + min(20, (hit_rate - 50) / 2)
        else:
            consistency_score = max(0, 30 - (cv - 60) / 2)
        
        # Reliability rating
        if consistency_score >= 85:
            reliability = 'Very High'
        elif consistency_score >= 70:
            reliability = 'High'
        elif consistency_score >= 55:
            reliability = 'Medium'
        elif consistency_score >= 40:
            reliability = 'Low'
        else:
            reliability = 'Very Low'
        
        return {
            'consistency_score': round(consistency_score, 1),
            'std_dev': round(std_dev, 2),
            'coefficient_variation': round(cv, 1),
            'hit_rate': round(hit_rate, 1),
            'reliability': reliability,
            'mean': round(mean_val, 1)
        }
    
    @staticmethod
    def calculate_reliability_score(
        player_name: str,
        prop_type: str,
        recent_games: List[float],
        line: float,
        edge_percent: float
    ) -> Dict:
        """
        Calculate comprehensive reliability score (0-100)
        Factors: consistency, player role, edge quality, sample size
        """
        player_lower = player_name.lower()
        score = 0
        factors = []
        
        # Base score from consistency (0-40 points)
        consistency = EnhancedBetAnalyzer.calculate_consistency_score(recent_games, line)
        consistency_points = consistency['consistency_score'] * 0.4
        score += consistency_points
        factors.append(f"Consistency: {consistency_points:.1f}/40")
        
        # Player role (0-25 points)
        role_points = 25  # Start at max
        
        # Penalize backups
        if player_lower in EnhancedBetAnalyzer.BACKUP_RBS:
            role_points = 5
            factors.append(f"Role: 5/25 (Backup RB)")
        elif player_lower in EnhancedBetAnalyzer.BACKUP_TES:
            role_points = 10
            factors.append(f"Role: 10/25 (Backup TE)")
        elif any(player_lower in committee for committee in EnhancedBetAnalyzer.COMMITTEE_BACKFIELDS.values()):
            role_points = 15
            factors.append(f"Role: 15/25 (Committee)")
        else:
            factors.append(f"Role: 25/25 (Starter)")
        
        score += role_points
        
        # Edge quality (0-20 points)
        if edge_percent >= 50:
            edge_points = 20
        elif edge_percent >= 30:
            edge_points = 18
        elif edge_percent >= 15:
            edge_points = 15
        elif edge_percent >= 8:
            edge_points = 12
        elif edge_percent >= 5:
            edge_points = 8
        elif edge_percent >= 3:
            edge_points = 5
        else:
            edge_points = 2
        
        score += edge_points
        factors.append(f"Edge: {edge_points}/20")
        
        # Sample size (0-15 points)
        if len(recent_games) >= 7:
            sample_points = 15
        elif len(recent_games) >= 5:
            sample_points = 12
        elif len(recent_games) >= 3:
            sample_points = 8
        else:
            sample_points = 3
        
        score += sample_points
        factors.append(f"Sample: {sample_points}/15")
        
        # Final reliability rating
        if score >= 85:
            rating = '🔥 Elite'
            color = '#22c55e'
        elif score >= 70:
            rating = '✅ High'
            color = '#3b82f6'
        elif score >= 55:
            rating = '⚡ Medium'
            color = '#f59e0b'
        elif score >= 40:
            rating = '⚠️ Low'
            color = '#f97316'
        else:
            rating = '❌ Very Low'
            color = '#ef4444'
        
        return {
            'reliability_score': round(score, 1),
            'rating': rating,
            'color': color,
            'factors': factors,
            'consistency': consistency
        }
    
    @staticmethod
    def adjust_for_game_script(
        projection: float,
        prop_type: str,
        team_spread: float,
        is_home: bool
    ) -> Tuple[float, str]:
        """
        Adjust projection based on expected game script
        team_spread: positive if favored, negative if underdog
        Returns: (adjusted_projection, explanation)
        """
        adjustment = 0
        explanation = ""
        
        # Heavy favorite (7+ point favorites)
        if team_spread >= 7:
            if 'rush' in prop_type:
                adjustment = 0.10  # 10% boost to rushing
                explanation = f"Heavy favorite (+{team_spread}) → More rushing expected"
            elif 'pass' in prop_type or 'reception' in prop_type:
                adjustment = -0.05  # 5% decrease to passing
                explanation = f"Heavy favorite (+{team_spread}) → Less passing expected"
        
        # Heavy underdog (7+ point underdogs)
        elif team_spread <= -7:
            if 'rush' in prop_type:
                adjustment = -0.10  # 10% decrease to rushing
                explanation = f"Heavy underdog ({team_spread}) → Less rushing expected"
            elif 'pass' in prop_type or 'reception' in prop_type:
                adjustment = 0.10  # 10% boost to passing
                explanation = f"Heavy underdog ({team_spread}) → More passing expected"
        
        # Moderate favorite (3-6 points)
        elif team_spread >= 3:
            if 'rush' in prop_type:
                adjustment = 0.05
                explanation = f"Moderate favorite (+{team_spread}) → Slight rushing boost"
            elif 'pass' in prop_type or 'reception' in prop_type:
                adjustment = -0.02
                explanation = f"Moderate favorite (+{team_spread}) → Slight passing decrease"
        
        # Moderate underdog (3-6 points)
        elif team_spread <= -3:
            if 'rush' in prop_type:
                adjustment = -0.05
                explanation = f"Moderate underdog ({team_spread}) → Slight rushing decrease"
            elif 'pass' in prop_type or 'reception' in prop_type:
                adjustment = 0.05
                explanation = f"Moderate underdog ({team_spread}) → Slight passing boost"
        
        adjusted = projection * (1 + adjustment)
        
        return adjusted, explanation
    
    @staticmethod
    def identify_parlay_correlations(bets: List[Dict]) -> List[Dict]:
        """
        Identify correlations in parlay legs
        Returns list of correlation warnings
        """
        warnings = []
        
        # Group by game
        games = {}
        for i, bet in enumerate(bets):
            game_key = bet.get('game', 'Unknown')
            if game_key not in games:
                games[game_key] = []
            games[game_key].append((i, bet))
        
        # Check for same-game concentration
        for game, game_bets in games.items():
            if len(game_bets) >= 3:
                warnings.append({
                    'type': 'same_game_concentration',
                    'severity': 'high',
                    'message': f"⚠️ {len(game_bets)} legs from same game ({game}). If game script goes wrong, multiple legs fail.",
                    'legs': [i for i, _ in game_bets]
                })
        
        # Check for same player multiple props
        player_counts = {}
        for i, bet in enumerate(bets):
            player = bet.get('player', '')
            if player not in player_counts:
                player_counts[player] = []
            player_counts[player].append(i)
        
        for player, legs in player_counts.items():
            if len(legs) >= 2:
                warnings.append({
                    'type': 'same_player',
                    'severity': 'medium',
                    'message': f"💡 {len(legs)} bets on {player}. Correlated - good if player has big game, bad if they don't.",
                    'legs': legs
                })
        
        # Check for passing TD + receiving yard correlation
        for i, bet1 in enumerate(bets):
            if 'pass_tds' in bet1.get('prop_type', ''):
                for j, bet2 in enumerate(bets):
                    if i != j and 'reception' in bet2.get('prop_type', ''):
                        warnings.append({
                            'type': 'qb_receiver_correlation',
                            'severity': 'low',
                            'message': f"✅ Positive correlation: QB TDs + Receiver yards from same team tend to hit together.",
                            'legs': [i, j]
                        })
        
        return warnings
    
    @staticmethod
    def filter_parlay_legs(bets: List[Dict], risk_level: str = 'conservative') -> List[Dict]:
        """
        Filter parlay legs based on risk level
        """
        filtered = []
        
        for bet in bets:
            reliability = bet.get('reliability_score', 50)
            player_lower = bet.get('player', '').lower()
            
            if risk_level == 'conservative':
                # Only very reliable bets
                if reliability < 70:
                    continue
                # No backups
                if player_lower in EnhancedBetAnalyzer.BACKUP_RBS:
                    continue
                if player_lower in EnhancedBetAnalyzer.BACKUP_TES:
                    continue
                # No committee backs
                if any(player_lower in committee for committee in EnhancedBetAnalyzer.COMMITTEE_BACKFIELDS.values()):
                    continue
                
            elif risk_level == 'balanced':
                # Medium-high reliability
                if reliability < 55:
                    continue
                # No backup TEs (but backup RBs ok if reliability is high)
                if player_lower in EnhancedBetAnalyzer.BACKUP_TES:
                    continue
            
            # Aggressive allows everything
            
            filtered.append(bet)
        
        return filtered
