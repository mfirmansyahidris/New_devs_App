import json
import redis.asyncio as redis
from typing import Dict, Any, Optional
import os

# Initialize Redis client (typically configured centrally).
redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

async def get_revenue_summary(
    property_id: str, tenant_id: str,
    month: Optional[int] = None, year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Fetches revenue summary, utilizing caching to improve performance.
    """
    cache_key = f"revenue:v2:{tenant_id}:{property_id}:all"
    if month is not None:
        # Keep this UTC reproduction separate from all-time and timezone-correct caches.
        cache_key = f"revenue:utc-repro:{tenant_id}:{property_id}:{year:04d}-{month:02d}"
    
    # Try to get from cache
    cached = await redis_client.get(cache_key)
    if cached:
        payload = json.loads(cached)
        if payload.get("tenant_id") == tenant_id and payload.get("property_id") == property_id:
            return payload
    
    # Revenue calculation is delegated to the reservation service.
    from app.services.reservations import calculate_total_revenue
    
    # Calculate revenue
    result = await calculate_total_revenue(property_id, tenant_id, month, year)
    
    # Cache the result for 5 minutes
    await redis_client.setex(cache_key, 300, json.dumps(result))
    
    return result
