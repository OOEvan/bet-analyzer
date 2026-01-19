"""
Simple stats caching to avoid Pro Football Reference rate limiting
Caches player stats in memory for 1 hour
"""

import time
from typing import Dict, List, Optional, Tuple

class StatsCache:
    """Cache for player statistics to reduce PFR requests"""
    
    def __init__(self, ttl_seconds: int = 3600):  # 1 hour default
        self.cache: Dict[str, Tuple[List[float], float]] = {}  # key -> (stats, timestamp)
        self.ttl = ttl_seconds
    
    def _make_key(self, player: str, stat_type: str) -> str:
        """Create cache key from player name and stat type"""
        return f"{player.lower().strip()}:{stat_type.lower()}"
    
    def get(self, player: str, stat_type: str) -> Optional[List[float]]:
        """
        Get cached stats for a player
        Returns None if not in cache or expired
        """
        key = self._make_key(player, stat_type)
        
        if key not in self.cache:
            return None
        
        stats, timestamp = self.cache[key]
        
        # Check if expired
        if time.time() - timestamp > self.ttl:
            del self.cache[key]
            return None
        
        return stats
    
    def set(self, player: str, stat_type: str, stats: List[float]):
        """Cache stats for a player"""
        key = self._make_key(player, stat_type)
        self.cache[key] = (stats, time.time())
    
    def clear(self):
        """Clear all cached data"""
        self.cache.clear()
    
    def size(self) -> int:
        """Return number of cached entries"""
        return len(self.cache)
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        current_time = time.time()
        expired = sum(1 for _, timestamp in self.cache.values() 
                     if current_time - timestamp > self.ttl)
        
        return {
            'total_entries': len(self.cache),
            'expired': expired,
            'active': len(self.cache) - expired,
            'ttl_seconds': self.ttl
        }


# Global cache instance
_stats_cache = StatsCache(ttl_seconds=3600)

def get_cached_stats(player: str, stat_type: str) -> Optional[List[float]]:
    """Get stats from cache"""
    return _stats_cache.get(player, stat_type)

def cache_stats(player: str, stat_type: str, stats: List[float]):
    """Store stats in cache"""
    _stats_cache.set(player, stat_type, stats)

def clear_cache():
    """Clear the cache"""
    _stats_cache.clear()

def get_cache_stats() -> Dict:
    """Get cache statistics"""
    return _stats_cache.get_stats()
