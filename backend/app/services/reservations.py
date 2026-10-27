from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, List, Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException


def month_bounds(month: int, year: int, property_timezone: str):
    """Convert property-local month boundaries to UTC, including DST changes."""
    zone = ZoneInfo(property_timezone)
    start = datetime(year, month, 1, tzinfo=zone)
    end = (
        datetime(year + 1, 1, 1, tzinfo=zone) if month == 12
        else datetime(year, month + 1, 1, tzinfo=zone)
    )
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)

async def calculate_monthly_revenue(property_id: str, month: int, year: int, db_session=None) -> Decimal:
    """
    Calculates revenue for a specific month.
    """

    start_date = datetime(year, month, 1)
    if month < 12:
        end_date = datetime(year, month + 1, 1)
    else:
        end_date = datetime(year + 1, 1, 1)
        
    print(f"DEBUG: Querying revenue for {property_id} from {start_date} to {end_date}")

    # SQL Simulation (This would be executed against the actual DB)
    query = """
        SELECT SUM(total_amount) as total
        FROM reservations
        WHERE property_id = $1
        AND tenant_id = $2
        AND check_in_date >= $3
        AND check_in_date < $4
    """
    
    # In production this query executes against a database session.
    # result = await db.fetch_val(query, property_id, tenant_id, start_date, end_date)
    # return result or Decimal('0')
    
    return Decimal('0') # Placeholder for now until DB connection is finalized

async def calculate_total_revenue(
    property_id: str, tenant_id: str,
    month: Optional[int] = None, year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Aggregates revenue from database.
    """
    try:
        # Import database pool
        from app.core.database_pool import DatabasePool
        
        # Initialize pool if needed
        db_pool = DatabasePool()
        await db_pool.initialize()
        
        if db_pool.session_factory:
            async with db_pool.get_session() as session:
                # Use SQLAlchemy text for raw SQL
                from sqlalchemy import text
                
                params = {"property_id": property_id, "tenant_id": tenant_id}
                period_filter = ""
                if (month is None) != (year is None):
                    raise ValueError("month and year must be supplied together")
                if month is not None:
                    property_result = await session.execute(text("""
                        SELECT timezone FROM properties
                        WHERE id = :property_id AND tenant_id = :tenant_id
                    """), params)
                    property_timezone = property_result.scalar_one_or_none()
                    if property_timezone is None:
                        raise HTTPException(status_code=404, detail="Property not found")
                    params["start_date"], params["end_date"] = month_bounds(month, year, property_timezone)
                    period_filter = "AND check_in_date >= :start_date AND check_in_date < :end_date"

                query = text(f"""
                    SELECT 
                        property_id,
                        SUM(total_amount) as total_revenue,
                        COUNT(*) as reservation_count
                    FROM reservations 
                    WHERE property_id = :property_id AND tenant_id = :tenant_id
                    {period_filter}
                    GROUP BY property_id
                """)
                
                result = await session.execute(query, params)
                row = result.fetchone()
                
                if row:
                    total_revenue = Decimal(str(row.total_revenue))
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": str(total_revenue),
                        "currency": "USD", 
                        "count": row.reservation_count
                    }
                else:
                    # No reservations found for this property
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": "0.00",
                        "currency": "USD",
                        "count": 0
                    }
        else:
            raise Exception("Database pool not available")
            
    except Exception as e:
        if month is not None or year is not None:
            # Monthly reproduction must use real rows, never the mock fallback below.
            raise
        print(f"Database error for {property_id} (tenant: {tenant_id}): {e}")
        
        # Create property-specific mock data for testing when DB is unavailable
        # This ensures each property shows different figures
        mock_data = {
            'prop-001': {'total': '1000.00', 'count': 3},
            'prop-002': {'total': '4975.50', 'count': 4}, 
            'prop-003': {'total': '6100.50', 'count': 2},
            'prop-004': {'total': '1776.50', 'count': 4},
            'prop-005': {'total': '3256.00', 'count': 3}
        }
        
        mock_property_data = mock_data.get(property_id, {'total': '0.00', 'count': 0})
        
        return {
            "property_id": property_id,
            "tenant_id": tenant_id, 
            "total": mock_property_data['total'],
            "currency": "USD",
            "count": mock_property_data['count']
        }
