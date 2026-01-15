"""
Chatbot Processor for Vehicle Management System
Handles natural language queries and returns relevant data using Groq AI.
"""

import re
import json
from datetime import datetime, timedelta, date, time
from django.db.models import Sum, Count, Avg, Q, F
from django.db.models.functions import TruncDate
from django.utils import timezone
from pytz import timezone as pytz_timezone

from vehicles.models import Vehicle, VehicleType, Firm
from trips.models import Trip
from fuel.models import FuelTransaction, FuelStation
from maintenance.models import Maintenance, MaintenanceType
from accounts.models import CustomUser
from accidents.models import Accident
from sor.models import SOR

# Groq AI Configuration
GROQ_API_KEY = "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"

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


class ChatbotProcessor:
    """Process user queries and return relevant VMS data using Groq AI."""
    
    def __init__(self, user):
        self.user = user
        self.ist = pytz_timezone('Asia/Kolkata')
        self.today = timezone.now().astimezone(self.ist).date()
        
        # Initialize Groq client
        if GROQ_AVAILABLE:
            self.groq_client = Groq(api_key=GROQ_API_KEY)
        else:
            self.groq_client = None
    
    def _get_intent_from_groq(self, query):
        """Use Groq AI to understand the intent of the query."""
        if not self.groq_client:
            return None
        
        try:
            system_prompt = """You are an intent classifier for a Vehicle Management System chatbot.
Analyze the user's query and return a JSON response with:
1. "intent": one of these exact values: "driver_kms", "vehicle_kms", "vehicle_status", "vehicle_info", "vehicle_type_count", "ongoing_trips", "completed_trips", "trips_by_distance", "fuel_consumption", "fuel_comparison", "suspicious_fuel", "fuel_efficiency", "maintenance", "driver_list", "vehicle_list", "trip_summary", "accidents", "top_drivers", "vehicle_usage", "sor_high_value", "sor_status", "help", "greeting", "unknown"
2. "time_period": one of "today", "yesterday", "week", "month", "year", or null
3. "specific_driver": driver name if mentioned, or null
4. "specific_vehicle": Extract ONLY the actual vehicle model name or plate number. Ignore words like "vehicle", "car", "the", "for", "of", "about", "fuel", "consumption", "compare", "suspicious". Examples: "Thar", "Alcazar", "Innova", "TN01AB1234". Return null if no specific vehicle mentioned.
5. "friendly_response": a brief friendly acknowledgment (1 sentence)
6. "compare_months": If user wants to compare months, return an array of ALL month names mentioned like ["august", "september", "october", "november"]. Can be 2, 3, or 4 months. Otherwise null.
7. "min_distance": If user mentions minimum distance/km like "above 90km", "more than 100km", "over 50kms", extract the number (90, 100, 50). Otherwise null.
8. "fuel_entries_count": If user mentions "last 2 fuel entries", "past 3 fuel", "between 2 fuel", extract the number. Otherwise null (defaults to 2).

IMPORTANT:
- Use "vehicle_kms" when user asks about kilometers/distance by vehicle, kms per vehicle, distance traveled by vehicles, or vehicle mileage summary
- Use "driver_kms" when user asks about kilometers/distance by driver, kms per driver, or driver distance
- Use "fuel_efficiency" when user asks about km/kms run between fuel entries, distance between fuel fills, mileage between refueling, how far vehicle ran from last fuel entries, or fuel efficiency calculation
- Use "trips_by_distance" when user asks about trips above/below/over/more than X kms/kilometers (e.g., "trips above 90km", "trips over 100 kms", "show trips more than 50km")
- Use "vehicle_type_count" when user asks about count of vehicle types, how many cars/trucks/bikes, vehicle category count, or types of vehicles
- Use "sor_high_value" when user asks about high value SOR, high goods value, expensive SOR, or valuable shipments
- Use "sor_status" when user asks about SOR status, pending SOR, completed SOR, or SOR summary
- Use "completed_trips" when user asks about completed trips, finished trips, or how many trips were completed
- Use "ongoing_trips" when user asks about current, active, or ongoing trips
- Use "trip_summary" for general trip statistics or summary
- Use "suspicious_fuel" when user asks about suspicious, duplicate, fraud, unusual, or anomaly fuel entries
- Use "fuel_comparison" when user wants to COMPARE fuel between months
- Use "fuel_consumption" for regular fuel queries without comparison
- "for the vehicle thar" → specific_vehicle should be "Thar" (not "the vehicle")
- Use "vehicle_info" when user asks about a SPECIFIC vehicle's details
- Use "vehicle_status" for general fleet status summary
- Use "vehicle_list" for listing all vehicles

ONLY return valid JSON, nothing else. Examples:
{"intent": "vehicle_type_count", "time_period": null, "specific_driver": null, "specific_vehicle": null, "compare_months": null, "min_distance": null, "fuel_entries_count": null, "friendly_response": "Here's the count of vehicles by type!"}
{"intent": "trips_by_distance", "time_period": null, "specific_driver": null, "specific_vehicle": null, "compare_months": null, "min_distance": 90, "fuel_entries_count": null, "friendly_response": "Here are trips above 90km!"}
{"intent": "fuel_efficiency", "time_period": null, "specific_driver": null, "specific_vehicle": "Thar", "compare_months": null, "min_distance": null, "fuel_entries_count": 2, "friendly_response": "Here's the distance covered between fuel entries!"}"""""

            response = self.groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            result = response.choices[0].message.content.strip()
            # Parse JSON response
            return json.loads(result)
        except Exception as e:
            print(f"Groq error: {e}")
            return None
        
    def process_query(self, query):
        """
        Main method to process a user query and return response.
        Uses Groq AI for intent detection, falls back to pattern matching.
        Returns a dict with 'message', 'data', and 'data_type'.
        """
        query_lower = query.lower().strip()
        
        # Try Groq AI first for better understanding
        groq_intent = self._get_intent_from_groq(query)
        
        if groq_intent:
            intent = groq_intent.get('intent')
            friendly_response = groq_intent.get('friendly_response', '')
            time_period = groq_intent.get('time_period')
            
            # Override query with time period if detected
            if time_period:
                query_lower = f"{query_lower} {time_period}"
            
            # Handle greeting
            if intent == 'greeting':
                return {
                    'message': f"👋 Hello! I'm your VMS Assistant. I can help you with:\n\n"
                              "• Driver kilometers and trip details\n"
                              "• Vehicle status and availability\n"
                              "• Fuel consumption reports\n"
                              "• Maintenance schedules\n"
                              "• Accident reports\n\n"
                              "What would you like to know?",
                    'data': None,
                    'data_type': 'text'
                }
            
            # Map intent to handler
            specific_vehicle = groq_intent.get('specific_vehicle')
            compare_months = groq_intent.get('compare_months')
            min_distance = groq_intent.get('min_distance')
            fuel_entries_count = groq_intent.get('fuel_entries_count') or 2
            
            intent_handlers = {
                'driver_kms': lambda: self._get_driver_kms(query_lower),
                'vehicle_kms': lambda: self._get_vehicle_kms(query_lower),
                'vehicle_status': lambda: self._get_vehicle_status(query_lower),
                'vehicle_info': lambda: self._get_vehicle_info(specific_vehicle or query_lower),
                'vehicle_type_count': lambda: self._get_vehicle_type_count(),
                'ongoing_trips': lambda: self._get_ongoing_trips(),
                'completed_trips': lambda: self._get_completed_trips(query_lower),
                'trips_by_distance': lambda: self._get_trips_by_distance(query_lower, min_distance),
                'fuel_consumption': lambda: self._get_fuel_consumption(query_lower),
                'fuel_comparison': lambda: self._get_fuel_comparison(compare_months, query_lower, specific_vehicle),
                'suspicious_fuel': lambda: self._get_suspicious_fuel(compare_months, query_lower, specific_vehicle),
                'fuel_efficiency': lambda: self._get_fuel_efficiency(query_lower, specific_vehicle, fuel_entries_count),
                'maintenance': lambda: self._get_maintenance_info(query_lower),
                'driver_list': lambda: self._get_driver_list(),
                'vehicle_list': lambda: self._get_vehicle_list(query_lower),
                'trip_summary': lambda: self._get_trip_summary(query_lower),
                'accidents': lambda: self._get_accident_info(query_lower),
                'top_drivers': lambda: self._get_top_drivers(query_lower),
                'vehicle_usage': lambda: self._get_vehicle_usage(query_lower),
                'sor_high_value': lambda: self._get_sor_high_value(query_lower),
                'sor_status': lambda: self._get_sor_status(query_lower),
                'help': lambda: self._get_help(),
            }
            
            if intent in intent_handlers:
                result = intent_handlers[intent]()
                # Prepend friendly response if available
                if friendly_response and result.get('message'):
                    result['message'] = f"{friendly_response}\n\n{result['message']}"
                return result
        
        # Fallback to pattern matching
        if self._matches_trips_by_distance(query_lower):
            return self._get_trips_by_distance(query_lower, None)
        elif self._matches_vehicle_kms(query_lower):
            return self._get_vehicle_kms(query_lower)
        elif self._matches_driver_kms(query_lower):
            return self._get_driver_kms(query_lower)
        elif self._matches_vehicle_status(query_lower):
            return self._get_vehicle_status(query_lower)
        elif self._matches_vehicle_type_count(query_lower):
            return self._get_vehicle_type_count()
        elif self._matches_vehicle_info(query_lower):
            return self._get_vehicle_info(query_lower)
        elif self._matches_completed_trips(query_lower):
            return self._get_completed_trips(query_lower)
        elif self._matches_ongoing_trips(query_lower):
            return self._get_ongoing_trips()
        elif self._matches_fuel_efficiency(query_lower):
            return self._get_fuel_efficiency(query_lower, None, 2)
        elif self._matches_suspicious_fuel(query_lower):
            return self._get_suspicious_fuel(None, query_lower, None)
        elif self._matches_fuel_consumption(query_lower):
            return self._get_fuel_consumption(query_lower)
        elif self._matches_maintenance(query_lower):
            return self._get_maintenance_info(query_lower)
        elif self._matches_driver_list(query_lower):
            return self._get_driver_list()
        elif self._matches_vehicle_list(query_lower):
            return self._get_vehicle_list(query_lower)
        elif self._matches_trip_summary(query_lower):
            return self._get_trip_summary(query_lower)
        elif self._matches_accidents(query_lower):
            return self._get_accident_info(query_lower)
        elif self._matches_top_drivers(query_lower):
            return self._get_top_drivers(query_lower)
        elif self._matches_vehicle_usage(query_lower):
            return self._get_vehicle_usage(query_lower)
        elif self._matches_sor_high_value(query_lower):
            return self._get_sor_high_value(query_lower)
        elif self._matches_sor_status(query_lower):
            return self._get_sor_status(query_lower)
        elif self._matches_help(query_lower):
            return self._get_help()
        else:
            return self._get_smart_response(query)
    
    # ==================== Intent Matchers ====================
    
    def _matches_vehicle_kms(self, query):
        patterns = [
            r'vehicle.*km', r'km.*vehicle', r'vehicle.*distance', r'distance.*vehicle',
            r'how much.*vehicle.*run', r'vehicle.*run', r'kms.*by.*vehicle',
            r'km.*by.*vehicle', r'kilometers.*vehicle', r'vehicle.*travel',
            r'kms.*per.*vehicle', r'distance.*per.*vehicle', r'each.*vehicle.*km',
            r'vehicle.*drove', r'mileage.*by.*vehicle'
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _matches_driver_kms(self, query):
        patterns = [
            r'driver.*km', r'km.*driver', r'driver.*distance', r'distance.*driver',
            r'how much.*driver.*run', r'driver.*run.*today', r'driver.*travel',
            r'kms.*run', r'kilometers.*driver', r'driver.*drove', r'who drove'
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _matches_vehicle_status(self, query):
        patterns = [
            r'vehicle.*status', r'status.*vehicle', r'how many.*vehicle',
            r'available.*vehicle', r'vehicle.*available', r'in use.*vehicle',
            r'maintenance.*vehicle', r'vehicle.*maintenance'
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _matches_vehicle_info(self, query):
        patterns = [
            r'odometer', r'current.*km', r'mileage.*of', r'details.*of',
            r'info.*about', r'about.*vehicle', r'what.*is.*the.*odometer',
            r'reading.*of', r'status.*of.*\w+', r'tell.*me.*about'
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _matches_vehicle_type_count(self, query):
        patterns = [
            r'count.*vehicle.*type', r'vehicle.*type.*count', r'how many.*type',
            r'type.*of.*vehicle', r'vehicle.*category', r'category.*count',
            r'how many.*car', r'how many.*truck', r'how many.*bike',
            r'types.*count', r'count.*types', r'breakdown.*vehicle'
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _matches_trips_by_distance(self, query):
        patterns = [
            r'trip.*above.*\d+', r'trip.*over.*\d+', r'trip.*more.*than.*\d+',
            r'trip.*greater.*\d+', r'trip.*exceed.*\d+', r'above.*\d+.*km',
            r'over.*\d+.*km', r'more.*than.*\d+.*km', r'\d+.*km.*trip'
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _matches_ongoing_trips(self, query):
        patterns = [
            r'ongoing.*trip', r'active.*trip', r'current.*trip',
            r'trip.*progress', r'who.*driving', r'trips.*now'
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _matches_completed_trips(self, query):
        patterns = [
            r'completed.*trip', r'finished.*trip', r'trip.*completed',
            r'trip.*finished', r'how many.*trip.*completed', r'trips.*done',
            r'done.*trip', r'complete.*trip'
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _matches_suspicious_fuel(self, query):
        patterns = [
            r'suspicious.*fuel', r'fuel.*suspicious', r'duplicate.*fuel',
            r'fuel.*fraud', r'fraud.*fuel', r'unusual.*fuel', r'fuel.*unusual',
            r'anomal.*fuel', r'fuel.*anomal', r'double.*fuel', r'fuel.*double'
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _matches_fuel_consumption(self, query):
        patterns = [
            r'fuel.*consumption', r'fuel.*cost', r'fuel.*expense',
            r'petrol', r'diesel', r'fuel.*usage', r'fuel.*today',
            r'fuel.*week', r'fuel.*month', r'how much fuel'
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _matches_fuel_efficiency(self, query):
        """Match queries about km run between fuel entries."""
        patterns = [
            r'km.*fuel.*entr', r'kms.*fuel.*entr', r'kilometer.*fuel',
            r'distance.*fuel.*entr', r'fuel.*entr.*km', r'fuel.*entr.*distance',
            r'between.*fuel', r'run.*fuel.*entr', r'mileage.*fuel',
            r'how.*far.*fuel', r'how.*much.*run.*fuel', r'vehicle.*run.*fuel',
            r'past.*\d+.*fuel', r'last.*\d+.*fuel', r'efficiency.*fuel'
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _matches_maintenance(self, query):
        patterns = [
            r'maintenance', r'repair', r'service.*due', r'scheduled.*service',
            r'vehicle.*service', r'pending.*maintenance'
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _matches_driver_list(self, query):
        patterns = [
            r'list.*driver', r'all.*driver', r'show.*driver', r'driver.*list',
            r'how many driver', r'number of driver'
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _matches_vehicle_list(self, query):
        patterns = [
            r'list.*vehicle', r'all.*vehicle', r'show.*vehicle', r'vehicle.*list',
            r'fleet', r'cars.*have', r'trucks.*have'
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _matches_trip_summary(self, query):
        patterns = [
            r'trip.*summary', r'trip.*report', r'total.*trip', r'trip.*count',
            r'completed.*trip', r'trip.*today', r'trip.*week', r'trip.*month'
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _matches_accidents(self, query):
        patterns = [
            r'accident', r'incident', r'crash', r'collision'
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _matches_top_drivers(self, query):
        patterns = [
            r'top.*driver', r'best.*driver', r'most.*km', r'highest.*km',
            r'driver.*ranking', r'driver.*leaderboard'
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _matches_vehicle_usage(self, query):
        patterns = [
            r'vehicle.*usage', r'most.*used.*vehicle', r'utilization',
            r'vehicle.*utilization', r'busy.*vehicle'
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _matches_sor_high_value(self, query):
        patterns = [
            r'high.*value.*sor', r'sor.*high.*value', r'expensive.*sor',
            r'sor.*expensive', r'high.*goods.*value', r'valuable.*sor',
            r'top.*sor', r'highest.*sor', r'big.*sor', r'large.*sor'
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _matches_sor_status(self, query):
        patterns = [
            r'sor.*status', r'status.*sor', r'pending.*sor', r'sor.*pending',
            r'sor.*summary', r'sor.*completed', r'completed.*sor', r'all.*sor',
            r'show.*sor', r'list.*sor'
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _matches_help(self, query):
        patterns = [r'help', r'what can you', r'how to', r'commands', r'what.*ask']
        return any(re.search(p, query) for p in patterns)
    
    # ==================== Date Helpers ====================
    
    def _parse_specific_date(self, query):
        """Parse specific dates from query like 19/08/2025, 2025-08-19, Aug 19 2025, 5th december, etc."""
        # Common date patterns
        date_patterns = [
            # DD/MM/YYYY or DD-MM-YYYY
            (r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', 'dmy'),
            # YYYY-MM-DD or YYYY/MM/DD
            (r'(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})', 'ymd'),
            # DD/MM/YY or DD-MM-YY
            (r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{2})\b', 'dmy_short'),
            # Month name patterns: Aug 19, 2025 or 19 Aug 2025
            (r'(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})', 'dmy_name'),
            (r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})', 'mdy_name'),
            # Ordinal patterns: 5th december, 1st january, 22nd march (with optional year)
            (r'(\d{1,2})(?:st|nd|rd|th)\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(?:\s+(\d{4}))?', 'ordinal_dmy'),
            # Month first with ordinal: december 5th, january 1st (with optional year)
            (r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s+(\d{4}))?', 'ordinal_mdy'),
        ]
        
        month_map = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        
        query_lower = query.lower()
        
        for pattern, format_type in date_patterns:
            match = re.search(pattern, query_lower)
            if match:
                try:
                    if format_type == 'dmy':
                        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    elif format_type == 'ymd':
                        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    elif format_type == 'dmy_short':
                        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                        year = 2000 + year if year < 100 else year
                    elif format_type == 'dmy_name':
                        day = int(match.group(1))
                        month = month_map.get(match.group(2)[:3], 1)
                        year = int(match.group(3))
                    elif format_type == 'mdy_name':
                        month = month_map.get(match.group(1)[:3], 1)
                        day = int(match.group(2))
                        year = int(match.group(3))
                    elif format_type == 'ordinal_dmy':
                        day = int(match.group(1))
                        month = month_map.get(match.group(2)[:3], 1)
                        year = int(match.group(3)) if match.group(3) else self.today.year
                        # If the date is in the future, use previous year
                        if date(year, month, day) > self.today:
                            year -= 1
                    elif format_type == 'ordinal_mdy':
                        month = month_map.get(match.group(1)[:3], 1)
                        day = int(match.group(2))
                        year = int(match.group(3)) if match.group(3) else self.today.year
                        # If the date is in the future, use previous year
                        if date(year, month, day) > self.today:
                            year -= 1
                    
                    return date(year, month, day)
                except (ValueError, TypeError):
                    continue
        
        return None
    
    def _get_date_range(self, query):
        """Extract date range from query."""
        today = self.today
        
        # Check for date range patterns like "from X to Y" or "between X and Y"
        # More specific patterns to capture full date strings
        from_to_patterns = [
            # Matches: "from 1st december to 30th december" or "from 1 dec 2025 to 30 dec 2025"
            r'from\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*(?:\s+\d{4})?)\s+to\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*(?:\s+\d{4})?)',
            # Matches: "from december 1st to december 30th"
            r'from\s+((?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+\d{4})?)\s+to\s+((?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+\d{4})?)',
            # Matches: "between 1st december and 30th december"
            r'between\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*(?:\s+\d{4})?)\s+and\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*(?:\s+\d{4})?)',
            # Matches: "from 01/12/2025 to 30/12/2025" or "from 2025-12-01 to 2025-12-30"
            r'from\s+(\d{1,4}[/\-]\d{1,2}[/\-]\d{1,4})\s+to\s+(\d{1,4}[/\-]\d{1,2}[/\-]\d{1,4})',
        ]
        
        for pattern in from_to_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                # Extract the two date parts
                date1_str = match.group(1).strip()
                date2_str = match.group(2).strip()
                
                # Parse both dates
                date1 = self._parse_specific_date(date1_str)
                date2 = self._parse_specific_date(date2_str)
                
                if date1 and date2:
                    # Return them in chronological order
                    if date1 <= date2:
                        return date1, date2
                    else:
                        return date2, date1
        
        # First try to parse a specific date
        specific_date = self._parse_specific_date(query)
        if specific_date:
            return specific_date, specific_date
        
        if 'today' in query:
            return today, today
        elif 'yesterday' in query:
            yesterday = today - timedelta(days=1)
            return yesterday, yesterday
        elif 'week' in query or 'last 7 days' in query:
            week_ago = today - timedelta(days=7)
            return week_ago, today
        elif 'month' in query or 'last 30 days' in query:
            month_ago = today - timedelta(days=30)
            return month_ago, today
        elif 'year' in query:
            year_start = date(today.year, 1, 1)
            return year_start, today
        else:
            # Default to today
            return today, today
    
    def _get_datetime_range(self, start_date, end_date):
        """Convert date range to datetime range with proper timezone."""
        start_dt = datetime.combine(start_date, time.min)
        end_dt = datetime.combine(end_date, time.max)
        
        start_dt = self.ist.localize(start_dt)
        end_dt = self.ist.localize(end_dt)
        
        return start_dt, end_dt
    
    # ==================== Data Handlers ====================
    
    def _get_vehicle_kms(self, query):
        """Get kilometers driven by each vehicle."""
        start_date, end_date = self._get_date_range(query)
        start_dt, end_dt = self._get_datetime_range(start_date, end_date)
        
        # Check if user wants fuel consumption included
        include_fuel = any(word in query.lower() for word in ['fuel', 'petrol', 'diesel', 'consumption', 'litres', 'liters'])
        
        # Get completed trips in the date range
        trips = Trip.objects.filter(
            status='completed',
            is_deleted=False,
            start_time__gte=start_dt,
            start_time__lte=end_dt,
            end_odometer__isnull=False,
            start_odometer__isnull=False
        ).select_related('vehicle')
        
        # Calculate KMs per vehicle
        vehicle_kms = {}
        for trip in trips:
            vehicle_id = trip.vehicle.id
            vehicle_key = f"{trip.vehicle.make} {trip.vehicle.model} ({trip.vehicle.license_plate})"
            kms = trip.end_odometer - trip.start_odometer
            if vehicle_key in vehicle_kms:
                vehicle_kms[vehicle_key]['kms'] += kms
                vehicle_kms[vehicle_key]['trips'] += 1
            else:
                vehicle_kms[vehicle_key] = {
                    'kms': kms,
                    'trips': 1,
                    'license_plate': trip.vehicle.license_plate,
                    'make': trip.vehicle.make,
                    'model': trip.vehicle.model,
                    'vehicle_id': vehicle_id,
                    'fuel_consumed': 0,
                    'fuel_cost': 0
                }
        
        # Get fuel consumption if requested
        if include_fuel:
            from fuel.models import FuelTransaction
            fuel_transactions = FuelTransaction.objects.filter(
                date__gte=start_date,
                date__lte=end_date
            ).values('vehicle_id').annotate(
                total_quantity=Sum('quantity'),
                total_cost=Sum('total_cost')
            )
            
            # Map fuel data to vehicles
            fuel_map = {ft['vehicle_id']: ft for ft in fuel_transactions}
            
            for vehicle_key, data in vehicle_kms.items():
                vehicle_id = data['vehicle_id']
                if vehicle_id in fuel_map:
                    data['fuel_consumed'] = fuel_map[vehicle_id]['total_quantity'] or 0
                    data['fuel_cost'] = fuel_map[vehicle_id]['total_cost'] or 0
        
        # Format for display
        date_range_text = self._format_date_range(start_date, end_date)
        
        if not vehicle_kms:
            return {
                'message': f"No completed trips found for {date_range_text}.",
                'data': None,
                'data_type': 'text'
            }
        
        # Sort by KMs descending
        sorted_vehicles = sorted(vehicle_kms.items(), key=lambda x: x[1]['kms'], reverse=True)
        
        table_data = []
        total_kms = 0
        total_fuel = 0
        total_fuel_cost = 0
        
        for vehicle_name, data in sorted_vehicles:
            row = {
                'Vehicle': f"{data['make']} {data['model']}",
                'License Plate': data['license_plate'],
                'KMs Driven': f"{data['kms']:,} km",
                'Trips': data['trips']
            }
            
            if include_fuel:
                row['Fuel Consumed'] = f"{data['fuel_consumed']:.1f} L" if data['fuel_consumed'] > 0 else 'N/A'
                row['Fuel Cost'] = f"₹{data['fuel_cost']:,.0f}" if data['fuel_cost'] > 0 else 'N/A'
                # Calculate mileage
                if data['fuel_consumed'] > 0 and data['kms'] > 0:
                    mileage = data['kms'] / data['fuel_consumed']
                    row['Mileage'] = f"{mileage:.1f} km/L"
                else:
                    row['Mileage'] = 'N/A'
                
                total_fuel += data['fuel_consumed']
                total_fuel_cost += data['fuel_cost']
            
            table_data.append(row)
            total_kms += data['kms']
        
        # Build summary message
        summary = f"🚗 Vehicle KMs for {date_range_text}:\n\nTotal: {total_kms:,} km by {len(vehicle_kms)} vehicles"
        
        if include_fuel:
            avg_mileage = total_kms / total_fuel if total_fuel > 0 else 0
            summary += f"\n⛽ Total Fuel: {total_fuel:.1f} L | Cost: ₹{total_fuel_cost:,.0f}"
            if avg_mileage > 0:
                summary += f" | Avg: {avg_mileage:.1f} km/L"
        
        return {
            'message': summary,
            'data': table_data,
            'data_type': 'table'
        }
    
    def _get_driver_kms(self, query):
        """Get kilometers driven by drivers."""
        start_date, end_date = self._get_date_range(query)
        start_dt, end_dt = self._get_datetime_range(start_date, end_date)
        
        # Get completed trips in the date range
        trips = Trip.objects.filter(
            status='completed',
            is_deleted=False,
            start_time__gte=start_dt,
            start_time__lte=end_dt,
            end_odometer__isnull=False
        ).select_related('driver', 'vehicle')
        
        # Calculate KMs per driver
        driver_kms = {}
        for trip in trips:
            driver_name = trip.driver.get_full_name()
            kms = trip.end_odometer - trip.start_odometer
            if driver_name in driver_kms:
                driver_kms[driver_name]['kms'] += kms
                driver_kms[driver_name]['trips'] += 1
            else:
                driver_kms[driver_name] = {
                    'kms': kms,
                    'trips': 1,
                    'driver_id': trip.driver.id
                }
        
        # Format for display
        date_range_text = self._format_date_range(start_date, end_date)
        
        if not driver_kms:
            return {
                'message': f"No completed trips found for {date_range_text}.",
                'data': None,
                'data_type': 'text'
            }
        
        # Sort by KMs descending
        sorted_drivers = sorted(driver_kms.items(), key=lambda x: x[1]['kms'], reverse=True)
        
        table_data = []
        total_kms = 0
        for driver_name, data in sorted_drivers:
            table_data.append({
                'Driver': driver_name,
                'KMs Driven': f"{data['kms']:,} km",
                'Trips': data['trips']
            })
            total_kms += data['kms']
        
        return {
            'message': f"📊 Driver KMs for {date_range_text}:\n\nTotal: {total_kms:,} km by {len(driver_kms)} drivers",
            'data': table_data,
            'data_type': 'table'
        }
    
    def _get_vehicle_status(self, query):
        """Get vehicle status summary."""
        status_counts = Vehicle.objects.values('status').annotate(count=Count('id'))
        
        status_display = {
            'available': '🟢 Available',
            'in_use': '🔵 In Use',
            'maintenance': '🟡 Under Maintenance',
            'retired': '⚫ Retired'
        }
        
        table_data = []
        total = 0
        for item in status_counts:
            status = item['status']
            count = item['count']
            total += count
            table_data.append({
                'Status': status_display.get(status, status.title()),
                'Count': count
            })
        
        return {
            'message': f"🚗 Vehicle Status Summary\n\nTotal Vehicles: {total}",
            'data': table_data,
            'data_type': 'table'
        }
    
    def _get_vehicle_info(self, search_term):
        """Get detailed information about a specific vehicle."""
        if not search_term:
            return {
                'message': "Please specify a vehicle name, model, or plate number.",
                'data': None,
                'data_type': 'text'
            }
        
        search_term = search_term.strip().lower()
        
        # Clean up common words that might be passed incorrectly
        ignore_words = ['the', 'vehicle', 'car', 'for', 'of', 'about', 'tell', 'me', 'show', 
                        'what', 'is', 'odometer', 'current', 'details', 'info', 'status',
                        'reading', 'km', 'mileage', 'a', 'an']
        
        # Extract meaningful words from search term
        words = search_term.split()
        meaningful_words = [w for w in words if w.lower() not in ignore_words and len(w) > 1]
        
        if meaningful_words:
            search_term = ' '.join(meaningful_words)
        
        # If search term is still generic, return helpful message
        if not search_term or search_term in ignore_words:
            return {
                'message': "🔍 Please specify a vehicle name (e.g., 'Thar', 'Alcazar', 'Innova') or plate number.",
                'data': None,
                'data_type': 'text'
            }
        
        # Search for vehicle by make, model, or license plate
        vehicles = Vehicle.objects.filter(
            Q(make__icontains=search_term) |
            Q(model__icontains=search_term) |
            Q(license_plate__icontains=search_term)
        ).select_related('vehicle_type')
        
        # If no results, try searching each word separately
        if not vehicles.exists() and len(meaningful_words) > 1:
            for word in meaningful_words:
                vehicles = Vehicle.objects.filter(
                    Q(make__icontains=word) |
                    Q(model__icontains=word) |
                    Q(license_plate__icontains=word)
                ).select_related('vehicle_type')
                if vehicles.exists():
                    break
        
        if not vehicles.exists():
            return {
                'message': f"🔍 No vehicle found matching '{search_term}'. Try searching by model name (e.g., Thar, Alcazar) or plate number.",
                'data': None,
                'data_type': 'text'
            }
        
        # If multiple vehicles match, show a list
        if vehicles.count() > 1:
            table_data = []
            for v in vehicles[:10]:
                status_icons = {
                    'available': '🟢',
                    'in_use': '🔵',
                    'maintenance': '🟡',
                    'retired': '⚫'
                }
                table_data.append({
                    'Vehicle': f"{v.make} {v.model}",
                    'Plate': v.license_plate,
                    'Odometer': f"{v.current_odometer:,} km",
                    'Status': f"{status_icons.get(v.status, '')} {v.get_status_display()}"
                })
            
            return {
                'message': f"🔍 Found {vehicles.count()} vehicles matching '{search_term}':",
                'data': table_data,
                'data_type': 'table'
            }
        
        # Single vehicle - show detailed info
        v = vehicles.first()
        status_icons = {
            'available': '🟢',
            'in_use': '🔵',
            'maintenance': '🟡',
            'retired': '⚫'
        }
        
        # Get last trip info
        last_trip = Trip.objects.filter(
            vehicle=v,
            status='completed',
            is_deleted=False
        ).order_by('-end_time').first()
        
        last_trip_info = "No trips recorded"
        if last_trip:
            last_trip_info = f"{last_trip.end_time.strftime('%d %b %Y')} - {last_trip.driver.get_full_name()}"
        
        # Build vehicle details
        table_data = [
            {'Field': '🚗 Vehicle', 'Value': f"{v.make} {v.model} ({v.year})"},
            {'Field': '🔢 License Plate', 'Value': v.license_plate},
            {'Field': '📊 Current Odometer', 'Value': f"{v.current_odometer:,} km"},
            {'Field': '📍 Status', 'Value': f"{status_icons.get(v.status, '')} {v.get_status_display()}"},
            {'Field': '🏷️ Type', 'Value': v.vehicle_type.name if v.vehicle_type else 'N/A'},
            {'Field': '🎨 Color', 'Value': v.color or 'N/A'},
            {'Field': '⛽ Fuel Type', 'Value': v.fuel_type or 'N/A'},
            {'Field': '👤 Assigned Driver', 'Value': v.assigned_driver or 'Not Assigned'},
            {'Field': '🕐 Last Trip', 'Value': last_trip_info},
        ]
        
        # Add insurance info if available
        if v.insurance_expiry_date:
            days_left = (v.insurance_expiry_date - self.today).days
            if days_left < 0:
                insurance_status = f"⚠️ Expired ({v.insurance_expiry_date.strftime('%d %b %Y')})"
            elif days_left < 30:
                insurance_status = f"⚠️ Expiring soon ({v.insurance_expiry_date.strftime('%d %b %Y')})"
            else:
                insurance_status = f"✅ Valid till {v.insurance_expiry_date.strftime('%d %b %Y')}"
            table_data.append({'Field': '📋 Insurance', 'Value': insurance_status})
        
        return {
            'message': f"🚗 Vehicle Details: {v.make} {v.model}",
            'data': table_data,
            'data_type': 'table'
        }

    def _get_ongoing_trips(self):
        """Get currently ongoing trips."""
        ongoing = Trip.objects.filter(
            status='ongoing',
            is_deleted=False
        ).select_related('driver', 'vehicle')
        
        if not ongoing.exists():
            return {
                'message': "✅ No ongoing trips at the moment.",
                'data': None,
                'data_type': 'text'
            }
        
        table_data = []
        for trip in ongoing:
            # Calculate duration
            duration = timezone.now() - trip.start_time
            hours = int(duration.total_seconds() // 3600)
            minutes = int((duration.total_seconds() % 3600) // 60)
            
            table_data.append({
                'Driver': trip.driver.get_full_name(),
                'Vehicle': f"{trip.vehicle.make} {trip.vehicle.model}",
                'Plate': trip.vehicle.license_plate,
                'From': trip.origin[:30],
                'Duration': f"{hours}h {minutes}m",
                'Purpose': trip.purpose[:25]
            })
        
        return {
            'message': f"🚗 Currently {ongoing.count()} Ongoing Trip(s)",
            'data': table_data,
            'data_type': 'table'
        }
    
    def _get_completed_trips(self, query):
        """Get completed trips for the specified time period."""
        start_date, end_date = self._get_date_range(query)
        start_dt, end_dt = self._get_datetime_range(start_date, end_date)
        
        completed = Trip.objects.filter(
            status='completed',
            is_deleted=False,
            end_time__gte=start_dt,
            end_time__lte=end_dt
        ).select_related('driver', 'vehicle').order_by('-end_time')
        
        if not completed.exists():
            date_range_text = self._format_date_range(start_date, end_date)
            return {
                'message': f"📋 No completed trips for {date_range_text}.",
                'data': None,
                'data_type': 'text'
            }
        
        # Calculate total KMs
        total_kms = 0
        table_data = []
        for trip in completed[:15]:  # Show up to 15 trips
            kms = 0
            if trip.end_odometer and trip.start_odometer:
                kms = trip.end_odometer - trip.start_odometer
                total_kms += kms
            
            # Calculate trip duration
            if trip.end_time and trip.start_time:
                duration = trip.end_time - trip.start_time
                hours = int(duration.total_seconds() // 3600)
                minutes = int((duration.total_seconds() % 3600) // 60)
                duration_str = f"{hours}h {minutes}m"
            else:
                duration_str = "N/A"
            
            table_data.append({
                'Driver': trip.driver.get_full_name()[:20] if trip.driver else 'N/A',
                'Vehicle': f"{trip.vehicle.make} {trip.vehicle.model}"[:20] if trip.vehicle else 'N/A',
                'From → To': f"{trip.origin[:12]} → {trip.destination[:12] if trip.destination else 'N/A'}",
                'KMs': f"{kms:,}" if kms > 0 else 'N/A',
                'Duration': duration_str,
                'End Time': trip.end_time.strftime('%H:%M') if trip.end_time else 'N/A'
            })
        
        date_range_text = self._format_date_range(start_date, end_date)
        count = completed.count()
        
        return {
            'message': f"✅ {count} Completed Trip(s) for {date_range_text}\n\n📏 Total Distance: {total_kms:,} KMs",
            'data': table_data,
            'data_type': 'table'
        }
    
    def _get_trips_by_distance(self, query, min_distance=None):
        """Get trips filtered by minimum distance (KM)."""
        start_date, end_date = self._get_date_range(query)
        start_dt, end_dt = self._get_datetime_range(start_date, end_date)
        
        # Extract min_distance from query if not provided
        if min_distance is None:
            # Try to extract number from query
            match = re.search(r'(\d+)\s*(?:km|kms|kilometer|kilometers)?', query)
            if match:
                min_distance = int(match.group(1))
            else:
                min_distance = 50  # Default to 50km if not specified
        
        # Get completed trips with valid odometer readings
        trips = Trip.objects.filter(
            status='completed',
            is_deleted=False,
            end_time__gte=start_dt,
            end_time__lte=end_dt,
            end_odometer__isnull=False,
            start_odometer__isnull=False
        ).select_related('driver', 'vehicle').order_by('-end_time')
        
        # Filter trips by distance and collect results
        filtered_trips = []
        for trip in trips:
            distance = trip.end_odometer - trip.start_odometer
            if distance >= min_distance:
                filtered_trips.append((trip, distance))
        
        # Sort by distance descending
        filtered_trips.sort(key=lambda x: x[1], reverse=True)
        
        date_range_text = self._format_date_range(start_date, end_date)
        
        if not filtered_trips:
            return {
                'message': f"📋 No trips found above {min_distance} KM for {date_range_text}.",
                'data': None,
                'data_type': 'text'
            }
        
        # Calculate total KMs
        total_kms = sum(dist for _, dist in filtered_trips)
        
        table_data = []
        for trip, distance in filtered_trips[:20]:  # Show up to 20 trips
            # Calculate trip duration
            if trip.end_time and trip.start_time:
                duration = trip.end_time - trip.start_time
                hours = int(duration.total_seconds() // 3600)
                minutes = int((duration.total_seconds() % 3600) // 60)
                duration_str = f"{hours}h {minutes}m"
            else:
                duration_str = "N/A"
            
            table_data.append({
                'Driver': trip.driver.get_full_name()[:20] if trip.driver else 'N/A',
                'Vehicle': f"{trip.vehicle.make} {trip.vehicle.model}"[:20] if trip.vehicle else 'N/A',
                'Plate': trip.vehicle.license_plate if trip.vehicle else 'N/A',
                'From → To': f"{trip.origin[:12]} → {trip.destination[:12] if trip.destination else 'N/A'}",
                'Distance': f"{distance:,} km",
                'Duration': duration_str,
            })
        
        count = len(filtered_trips)
        
        return {
            'message': f"🚗 {count} Trip(s) Above {min_distance} KM for {date_range_text}\n\n📏 Total Distance: {total_kms:,} KMs",
            'data': table_data,
            'data_type': 'table'
        }
    
    def _get_fuel_consumption(self, query):
        """Get fuel consumption data."""
        start_date, end_date = self._get_date_range(query)
        
        transactions = FuelTransaction.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).select_related('vehicle', 'driver')
        
        if not transactions.exists():
            date_range_text = self._format_date_range(start_date, end_date)
            return {
                'message': f"No fuel transactions found for {date_range_text}.",
                'data': None,
                'data_type': 'text'
            }
        
        # Aggregate data
        total_cost = transactions.aggregate(total=Sum('total_cost'))['total'] or 0
        total_quantity = transactions.aggregate(total=Sum('quantity'))['total'] or 0
        
        # Group by vehicle
        vehicle_fuel = transactions.values(
            'vehicle__make', 'vehicle__model', 'vehicle__license_plate'
        ).annotate(
            total_cost=Sum('total_cost'),
            total_quantity=Sum('quantity')
        ).order_by('-total_cost')[:10]
        
        table_data = []
        for vf in vehicle_fuel:
            table_data.append({
                'Vehicle': f"{vf['vehicle__make']} {vf['vehicle__model']}",
                'Plate': vf['vehicle__license_plate'],
                'Quantity': f"{vf['total_quantity']:.1f} L" if vf['total_quantity'] else 'N/A',
                'Cost': f"₹{vf['total_cost']:,.2f}"
            })
        
        date_range_text = self._format_date_range(start_date, end_date)
        return {
            'message': f"⛽ Fuel Consumption for {date_range_text}\n\nTotal: {total_quantity:.1f} L | Cost: ₹{total_cost:,.2f}",
            'data': table_data,
            'data_type': 'table'
        }
    
    def _get_fuel_efficiency(self, query, specific_vehicle=None, num_entries=2):
        """Calculate km run between fuel entries for vehicles."""
        # Find vehicle if specified
        vehicle_filter = Q()
        vehicle_name = ""
        
        if specific_vehicle:
            # Search by license plate or make/model
            vehicle_filter = (
                Q(vehicle__license_plate__icontains=specific_vehicle) |
                Q(vehicle__make__icontains=specific_vehicle) |
                Q(vehicle__model__icontains=specific_vehicle)
            )
            vehicle_name = specific_vehicle
        
        # Get all vehicles with fuel transactions
        if specific_vehicle:
            vehicles = Vehicle.objects.filter(
                Q(license_plate__icontains=specific_vehicle) |
                Q(make__icontains=specific_vehicle) |
                Q(model__icontains=specific_vehicle)
            ).distinct()
        else:
            # Get vehicles that have fuel transactions
            vehicles = Vehicle.objects.filter(
                fuel_transactions__isnull=False
            ).distinct()[:10]  # Limit to 10 vehicles for overview
        
        if not vehicles.exists():
            return {
                'message': f"🔍 No vehicles found{' matching: ' + specific_vehicle if specific_vehicle else ''}.",
                'data': None,
                'data_type': 'text'
            }
        
        table_data = []
        total_km = 0
        total_fuel = 0
        
        for vehicle in vehicles:
            # Get last N fuel transactions for this vehicle, ordered by date/odometer
            fuel_entries = FuelTransaction.objects.filter(
                vehicle=vehicle,
                odometer_reading__isnull=False
            ).order_by('-date', '-id')[:num_entries]
            
            fuel_list = list(fuel_entries)
            
            if len(fuel_list) < 2:
                # Not enough entries with odometer readings
                continue
            
            # Calculate distance between entries
            # Latest entry (first in list) vs previous entry (second in list)
            latest = fuel_list[0]
            previous = fuel_list[1]
            
            if latest.odometer_reading and previous.odometer_reading:
                km_run = latest.odometer_reading - previous.odometer_reading
                
                # Get fuel quantity for the latest entry (fuel used to cover this distance)
                fuel_used = float(latest.quantity) if latest.quantity else 0
                
                # Calculate mileage
                mileage = km_run / fuel_used if fuel_used > 0 else 0
                
                # Get days between entries
                days_diff = (latest.date - previous.date).days if latest.date and previous.date else 0
                
                table_data.append({
                    'Vehicle': f"{vehicle.make} {vehicle.model}",
                    'Plate': vehicle.license_plate,
                    'Prev Odo': f"{previous.odometer_reading:,.0f} km",
                    'Curr Odo': f"{latest.odometer_reading:,.0f} km",
                    'KM Run': f"{km_run:,.0f} km",
                    'Fuel': f"{fuel_used:.1f} L",
                    'Mileage': f"{mileage:.1f} km/L",
                    'Days': str(days_diff)
                })
                
                total_km += km_run
                total_fuel += fuel_used
        
        if not table_data:
            return {
                'message': f"📊 No fuel entries with odometer readings found{' for ' + specific_vehicle if specific_vehicle else ''}.\n\nTip: Ensure odometer readings are recorded during fuel entries.",
                'data': None,
                'data_type': 'text'
            }
        
        avg_mileage = total_km / total_fuel if total_fuel > 0 else 0
        
        summary_msg = f"🚗 Distance between last {num_entries} fuel entries"
        if specific_vehicle:
            summary_msg += f" for {specific_vehicle}"
        summary_msg += f"\n\n📊 Total: {total_km:,.0f} km | ⛽ Fuel: {total_fuel:.1f} L | 📈 Avg Mileage: {avg_mileage:.1f} km/L"
        
        return {
            'message': summary_msg,
            'data': table_data,
            'data_type': 'table'
        }
    
    def _get_fuel_comparison(self, compare_months, query, specific_vehicle=None):
        """Compare fuel consumption between multiple months vehicle-wise."""
        from calendar import monthrange
        
        # Month name to number mapping
        month_map = {
            'january': 1, 'jan': 1,
            'february': 2, 'feb': 2,
            'march': 3, 'mar': 3,
            'april': 4, 'apr': 4,
            'may': 5,
            'june': 6, 'jun': 6,
            'july': 7, 'jul': 7,
            'august': 8, 'aug': 8,
            'september': 9, 'sep': 9, 'sept': 9,
            'october': 10, 'oct': 10,
            'november': 11, 'nov': 11,
            'december': 12, 'dec': 12
        }
        
        # Parse months from compare_months or query
        months_to_compare = []  # List of (month_num, month_name)
        
        if compare_months and len(compare_months) >= 2:
            for m in compare_months:
                m_lower = m.lower()
                m_num = month_map.get(m_lower)
                if m_num and (m_num, m_lower) not in [(x[0], x[1]) for x in months_to_compare]:
                    months_to_compare.append((m_num, m_lower))
        
        # If not enough months found, try to extract from query
        if len(months_to_compare) < 2:
            query_lower = query.lower()
            found_months = {}
            for month_name, month_num in month_map.items():
                if month_name in query_lower and len(month_name) > 2:
                    # Keep longer name if duplicate (august vs aug)
                    if month_num not in found_months or len(month_name) > len(found_months[month_num]):
                        found_months[month_num] = month_name
            
            months_to_compare = sorted([(num, name) for num, name in found_months.items()])
        
        if len(months_to_compare) < 2:
            return {
                'message': "🔍 Please specify at least two months to compare. Example: 'Compare August, September, October fuel consumption'",
                'data': None,
                'data_type': 'text'
            }
        
        # Limit to 4 months for readability
        months_to_compare = months_to_compare[:4]
        
        # Determine year for each month
        current_year = self.today.year
        month_dates = []
        for month_num, month_name in months_to_compare:
            year = current_year if month_num <= self.today.month else current_year - 1
            month_start = date(year, month_num, 1)
            month_end = date(year, month_num, monthrange(year, month_num)[1])
            month_dates.append({
                'num': month_num,
                'name': month_name,
                'year': year,
                'start': month_start,
                'end': month_end,
                'display': month_name.title()[:3]
            })
        
        # Add vehicle filter if specific vehicle is requested
        vehicle_filter = Q()
        vehicle_name_display = None
        if specific_vehicle:
            clean_vehicle = specific_vehicle.strip().lower()
            ignore_words = ['the', 'vehicle', 'car', 'for', 'of', 'about', 'fuel', 'consumption', 'compare', 'and']
            words = clean_vehicle.split()
            meaningful_words = [w for w in words if w not in ignore_words and len(w) > 1]
            if meaningful_words:
                clean_vehicle = ' '.join(meaningful_words)
            
            vehicle_filter = (
                Q(vehicle__make__icontains=clean_vehicle) |
                Q(vehicle__model__icontains=clean_vehicle) |
                Q(vehicle__license_plate__icontains=clean_vehicle)
            )
            vehicle_name_display = clean_vehicle.title()
        
        # Get fuel data for each month
        vehicle_comparison = {}
        month_totals = {}
        
        for i, md in enumerate(month_dates):
            month_key = f'month{i+1}'
            month_filter = Q(date__gte=md['start'], date__lte=md['end'])
            
            query_set = FuelTransaction.objects.filter(month_filter)
            if vehicle_filter:
                query_set = query_set.filter(vehicle_filter)
            
            month_data = query_set.values(
                'vehicle__id', 'vehicle__make', 'vehicle__model', 'vehicle__license_plate'
            ).annotate(
                total_quantity=Sum('quantity'),
                total_cost=Sum('total_cost')
            )
            
            month_totals[month_key] = {'qty': 0, 'cost': 0}
            
            for item in month_data:
                vid = item['vehicle__id']
                qty = item['total_quantity'] or 0
                cost = item['total_cost'] or 0
                
                month_totals[month_key]['qty'] += qty
                month_totals[month_key]['cost'] += cost
                
                if vid not in vehicle_comparison:
                    vehicle_comparison[vid] = {
                        'vehicle': f"{item['vehicle__make']} {item['vehicle__model']}",
                        'plate': item['vehicle__license_plate'],
                    }
                    # Initialize all months to 0
                    for j in range(len(month_dates)):
                        vehicle_comparison[vid][f'month{j+1}_qty'] = 0
                        vehicle_comparison[vid][f'month{j+1}_cost'] = 0
                
                vehicle_comparison[vid][f'{month_key}_qty'] = qty
                vehicle_comparison[vid][f'{month_key}_cost'] = cost
        
        # Ensure all vehicles have all month fields
        for vid, v_data in vehicle_comparison.items():
            for j in range(len(month_dates)):
                if f'month{j+1}_qty' not in v_data:
                    v_data[f'month{j+1}_qty'] = 0
                    v_data[f'month{j+1}_cost'] = 0
        
        if not vehicle_comparison:
            month_names = ', '.join([md['name'].title() for md in month_dates])
            if vehicle_name_display:
                return {
                    'message': f"🔍 No fuel data found for '{vehicle_name_display}' in {month_names}.",
                    'data': None,
                    'data_type': 'text'
                }
            return {
                'message': f"No fuel data found for {month_names}.",
                'data': None,
                'data_type': 'text'
            }
        
        # Build table data
        table_data = []
        
        # Sort by total consumption across all months
        sorted_vehicles = sorted(
            vehicle_comparison.values(),
            key=lambda x: sum(x.get(f'month{j+1}_qty', 0) for j in range(len(month_dates))),
            reverse=True
        )
        
        for v in sorted_vehicles:
            row = {'Vehicle': v['vehicle']}
            for i, md in enumerate(month_dates):
                qty = v.get(f'month{i+1}_qty', 0)
                row[f"{md['display']} (L)"] = f"{qty:.1f}"
            
            # Calculate change between first and last month
            first_qty = v.get('month1_qty', 0)
            last_qty = v.get(f'month{len(month_dates)}_qty', 0)
            diff = last_qty - first_qty
            diff_indicator = "📈" if diff > 0 else ("📉" if diff < 0 else "➡️")
            row['Change'] = f"{diff_indicator} {abs(diff):.1f}L"
            
            table_data.append(row)
        
        # Build summary message
        month_names_list = [md['name'].title() for md in month_dates]
        year = month_dates[0]['year']
        
        if vehicle_name_display:
            title = f"⛽ Fuel Comparison for {vehicle_name_display}: {' vs '.join(month_names_list)} {year}"
            vehicle_count_text = f"📋 Showing {len(vehicle_comparison)} matching vehicle(s)"
        else:
            title = f"⛽ Fuel Comparison: {' vs '.join(month_names_list)} {year}"
            vehicle_count_text = f"📋 Showing all {len(vehicle_comparison)} vehicles"
        
        # Build month-by-month totals
        totals_text = ""
        for i, md in enumerate(month_dates):
            month_key = f'month{i+1}'
            qty = month_totals.get(month_key, {}).get('qty', 0)
            cost = month_totals.get(month_key, {}).get('cost', 0)
            totals_text += f"📊 {md['name'].title()}: {qty:,.1f}L (₹{cost:,.0f})\n"
        
        # Overall trend (first vs last month)
        first_total = month_totals.get('month1', {}).get('qty', 0)
        last_total = month_totals.get(f'month{len(month_dates)}', {}).get('qty', 0)
        diff_total = last_total - first_total
        diff_percent = ((diff_total / first_total) * 100) if first_total > 0 else 0
        trend = "📈 increased" if diff_total > 0 else ("📉 decreased" if diff_total < 0 else "remained same")
        
        return {
            'message': f"{title}\n\n{totals_text}"
                      f"📈 Overall: Consumption {trend} by {abs(diff_total):,.1f}L ({abs(diff_percent):.1f}%) from {month_names_list[0]} to {month_names_list[-1]}\n"
                      f"{vehicle_count_text}",
            'data': table_data,
            'data_type': 'table'
        }

    def _get_suspicious_fuel(self, compare_months, query, specific_vehicle=None):
        """Detect suspicious fuel entries - same vehicle with fuel entries within 1-2 days."""
        from calendar import monthrange
        from collections import defaultdict
        
        # Month name to number mapping
        month_map = {
            'january': 1, 'jan': 1,
            'february': 2, 'feb': 2,
            'march': 3, 'mar': 3,
            'april': 4, 'apr': 4,
            'may': 5,
            'june': 6, 'jun': 6,
            'july': 7, 'jul': 7,
            'august': 8, 'aug': 8,
            'september': 9, 'sep': 9, 'sept': 9,
            'october': 10, 'oct': 10,
            'november': 11, 'nov': 11,
            'december': 12, 'dec': 12
        }
        
        # Parse month from compare_months or query
        target_month = None
        target_month_name = None
        
        if compare_months and len(compare_months) >= 1:
            m_lower = compare_months[0].lower()
            target_month = month_map.get(m_lower)
            target_month_name = m_lower
        
        # If no month found, try to extract from query
        if not target_month:
            query_lower = query.lower()
            for month_name, month_num in month_map.items():
                if month_name in query_lower and len(month_name) > 2:
                    target_month = month_num
                    target_month_name = month_name
                    break
        
        # Default to current month if no month specified
        if not target_month:
            target_month = self.today.month
            target_month_name = date(2000, target_month, 1).strftime('%B').lower()
        
        # Determine year
        current_year = self.today.year
        year = current_year if target_month <= self.today.month else current_year - 1
        
        # Get date range
        month_start = date(year, target_month, 1)
        month_end = date(year, target_month, monthrange(year, target_month)[1])
        
        # Add vehicle filter if specific vehicle is requested
        vehicle_filter = Q()
        vehicle_name_display = None
        if specific_vehicle:
            clean_vehicle = specific_vehicle.strip().lower()
            ignore_words = ['the', 'vehicle', 'car', 'for', 'of', 'about', 'fuel', 'consumption', 'suspicious', 'entries', 'and']
            words = clean_vehicle.split()
            meaningful_words = [w for w in words if w not in ignore_words and len(w) > 1]
            if meaningful_words:
                clean_vehicle = ' '.join(meaningful_words)
            
            vehicle_filter = (
                Q(vehicle__make__icontains=clean_vehicle) |
                Q(vehicle__model__icontains=clean_vehicle) |
                Q(vehicle__license_plate__icontains=clean_vehicle)
            )
            vehicle_name_display = clean_vehicle.title()
        
        # Get all fuel transactions for the month
        fuel_query = FuelTransaction.objects.filter(
            date__gte=month_start,
            date__lte=month_end
        )
        
        if vehicle_filter:
            fuel_query = fuel_query.filter(vehicle_filter)
        
        fuel_entries = fuel_query.order_by('vehicle__id', 'date').select_related('vehicle', 'driver')
        
        # Group fuel entries by vehicle
        vehicle_entries = defaultdict(list)
        for entry in fuel_entries:
            vehicle_key = entry.vehicle.id
            vehicle_entries[vehicle_key].append({
                'id': entry.id,
                'date': entry.date,
                'quantity': entry.quantity or 0,
                'cost': entry.total_cost or 0,
                'driver': f"{entry.driver.first_name} {entry.driver.last_name}" if entry.driver else "Unknown",
                'vehicle_name': f"{entry.vehicle.make} {entry.vehicle.model}",
                'plate': entry.vehicle.license_plate,
                'odometer': entry.odometer_reading or 0
            })
        
        # Find suspicious entries - same vehicle with fuel within 1-2 days
        suspicious_pairs = []
        max_days_gap = 2  # Flag entries within 2 days of each other
        
        for vehicle_id, entries in vehicle_entries.items():
            if len(entries) < 2:
                continue
            
            # Sort by date
            entries_sorted = sorted(entries, key=lambda x: x['date'])
            
            for i in range(len(entries_sorted) - 1):
                entry1 = entries_sorted[i]
                entry2 = entries_sorted[i + 1]
                
                days_apart = (entry2['date'] - entry1['date']).days
                
                if days_apart <= max_days_gap:
                    suspicious_pairs.append({
                        'vehicle': entry1['vehicle_name'],
                        'plate': entry1['plate'],
                        'date1': entry1['date'],
                        'date2': entry2['date'],
                        'days_apart': days_apart,
                        'qty1': entry1['quantity'],
                        'qty2': entry2['quantity'],
                        'cost1': entry1['cost'],
                        'cost2': entry2['cost'],
                        'driver1': entry1['driver'],
                        'driver2': entry2['driver'],
                        'odo1': entry1['odometer'],
                        'odo2': entry2['odometer']
                    })
        
        month_display = target_month_name.title()
        
        if not suspicious_pairs:
            if vehicle_name_display:
                msg = f"✅ Great news! No suspicious fuel entries found for '{vehicle_name_display}' in {month_display} {year}.\n\nNo same-vehicle fuel entries within 1-2 days were detected."
            else:
                msg = f"✅ Great news! No suspicious fuel entries found in {month_display} {year}.\n\nNo same-vehicle fuel entries within 1-2 days were detected."
            
            return {
                'message': msg,
                'data': None,
                'data_type': 'text'
            }
        
        # Build table data
        table_data = []
        total_suspicious_cost = 0
        
        for pair in suspicious_pairs:
            total_suspicious_cost += pair['cost1'] + pair['cost2']
            
            # Create row
            row = {
                'Vehicle': pair['vehicle'],
                'Entry 1': f"{pair['date1'].strftime('%d/%m')} - {pair['qty1']:.1f}L (₹{pair['cost1']:.0f})",
                'Entry 2': f"{pair['date2'].strftime('%d/%m')} - {pair['qty2']:.1f}L (₹{pair['cost2']:.0f})",
                'Gap': f"{pair['days_apart']} day(s)",
                'Drivers': f"{pair['driver1'][:10]} / {pair['driver2'][:10]}"
            }
            table_data.append(row)
        
        # Sort by days apart (most suspicious first)
        table_data = sorted(table_data, key=lambda x: int(x['Gap'].split()[0]))
        
        # Build summary
        if vehicle_name_display:
            title = f"⚠️ Suspicious Fuel Entries for {vehicle_name_display} - {month_display} {year}"
        else:
            title = f"⚠️ Suspicious Fuel Entries - {month_display} {year}"
        
        summary = (
            f"\n🔍 Found {len(suspicious_pairs)} suspicious pair(s) of fuel entries\n"
            f"📋 Same vehicle fueled within 1-2 days\n"
            f"💰 Total involved amount: ₹{total_suspicious_cost:,.0f}\n\n"
            f"⚡ Entries with 0 days gap are same-day refuels (most suspicious)\n"
            f"⚡ Entries with 1-2 days gap may need review"
        )
        
        return {
            'message': f"{title}{summary}",
            'data': table_data,
            'data_type': 'table'
        }

    def _get_maintenance_info(self, query):
        """Get maintenance information."""
        # Get pending and in-progress maintenance
        maintenance = Maintenance.objects.filter(
            status__in=['scheduled', 'in_progress']
        ).select_related('vehicle', 'maintenance_type')
        
        if not maintenance.exists():
            return {
                'message': "✅ No pending maintenance scheduled.",
                'data': None,
                'data_type': 'text'
            }
        
        table_data = []
        for m in maintenance[:15]:
            table_data.append({
                'Vehicle': f"{m.vehicle.make} {m.vehicle.model}",
                'Plate': m.vehicle.license_plate,
                'Type': m.maintenance_type.name,
                'Status': m.get_status_display(),
                'Scheduled': m.scheduled_date.strftime('%d-%b-%Y') if m.scheduled_date else 'TBD'
            })
        
        return {
            'message': f"🔧 Pending Maintenance: {maintenance.count()} item(s)",
            'data': table_data,
            'data_type': 'table'
        }
    
    def _get_driver_list(self):
        """Get list of all drivers."""
        drivers = CustomUser.objects.filter(
            user_type='driver',
            is_active=True,
            approval_status='approved'
        ).order_by('first_name', 'last_name')
        
        if not drivers.exists():
            return {
                'message': "No approved drivers found.",
                'data': None,
                'data_type': 'text'
            }
        
        table_data = []
        for driver in drivers[:20]:
            # Count trips
            trip_count = Trip.objects.filter(driver=driver, is_deleted=False).count()
            table_data.append({
                'Name': driver.get_full_name(),
                'Phone': driver.phone_number or 'N/A',
                'License': driver.license_number or 'N/A',
                'Total Trips': trip_count
            })
        
        return {
            'message': f"👥 Driver List ({drivers.count()} total approved drivers)",
            'data': table_data,
            'data_type': 'table'
        }
    
    def _get_vehicle_type_count(self):
        """Get count of vehicles grouped by vehicle type."""
        from django.db.models import Count
        
        # Get vehicle counts by type
        type_counts = Vehicle.objects.values(
            'vehicle_type__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')
        
        if not type_counts:
            return {
                'message': "❌ No vehicles found in the system.",
                'data': None,
                'data_type': 'text'
            }
        
        total_vehicles = sum(tc['count'] for tc in type_counts)
        
        table_data = []
        for tc in type_counts:
            type_name = tc['vehicle_type__name'] or 'Unknown'
            count = tc['count']
            percentage = (count / total_vehicles * 100) if total_vehicles > 0 else 0
            table_data.append({
                'Vehicle Type': type_name,
                'Count': count,
                'Percentage': f"{percentage:.1f}%"
            })
        
        # Add total row
        table_data.append({
            'Vehicle Type': '📊 TOTAL',
            'Count': total_vehicles,
            'Percentage': '100%'
        })
        
        return {
            'message': f"🚗 Vehicle Count by Type ({len(type_counts)} types)",
            'data': table_data,
            'data_type': 'table'
        }
    
    def _get_vehicle_list(self, query):
        """Get list of vehicles."""
        vehicles = Vehicle.objects.all().select_related('vehicle_type')
        
        # Filter by status if mentioned
        if 'available' in query:
            vehicles = vehicles.filter(status='available')
        elif 'in use' in query or 'in_use' in query:
            vehicles = vehicles.filter(status='in_use')
        elif 'maintenance' in query:
            vehicles = vehicles.filter(status='maintenance')
        
        if not vehicles.exists():
            return {
                'message': "No vehicles found matching your criteria.",
                'data': None,
                'data_type': 'text'
            }
        
        table_data = []
        for v in vehicles[:20]:
            status_icons = {
                'available': '🟢',
                'in_use': '🔵',
                'maintenance': '🟡',
                'retired': '⚫'
            }
            table_data.append({
                'Vehicle': f"{v.make} {v.model} ({v.year})",
                'Plate': v.license_plate,
                'Type': v.vehicle_type.name,
                'Status': f"{status_icons.get(v.status, '')} {v.get_status_display()}"
            })
        
        return {
            'message': f"🚗 Vehicle List ({vehicles.count()} total)",
            'data': table_data,
            'data_type': 'table'
        }
    
    def _get_trip_summary(self, query):
        """Get trip summary statistics."""
        start_date, end_date = self._get_date_range(query)
        start_dt, end_dt = self._get_datetime_range(start_date, end_date)
        
        trips = Trip.objects.filter(
            start_time__gte=start_dt,
            start_time__lte=end_dt,
            is_deleted=False
        )
        
        total = trips.count()
        completed = trips.filter(status='completed').count()
        ongoing = trips.filter(status='ongoing').count()
        cancelled = trips.filter(status='cancelled').count()
        
        # Calculate total KMs
        completed_trips = trips.filter(
            status='completed',
            end_odometer__isnull=False
        )
        total_kms = sum(
            t.end_odometer - t.start_odometer 
            for t in completed_trips 
            if t.end_odometer and t.start_odometer
        )
        
        date_range_text = self._format_date_range(start_date, end_date)
        
        table_data = [
            {'Metric': '📊 Total Trips', 'Value': total},
            {'Metric': '✅ Completed', 'Value': completed},
            {'Metric': '🚗 Ongoing', 'Value': ongoing},
            {'Metric': '❌ Cancelled', 'Value': cancelled},
            {'Metric': '📏 Total KMs', 'Value': f"{total_kms:,} km"},
        ]
        
        return {
            'message': f"📋 Trip Summary for {date_range_text}",
            'data': table_data,
            'data_type': 'table'
        }
    
    def _get_accident_info(self, query):
        """Get accident information."""
        start_date, end_date = self._get_date_range(query)
        start_dt, end_dt = self._get_datetime_range(start_date, end_date)
        
        accidents = Accident.objects.filter(
            date_time__gte=start_dt,
            date_time__lte=end_dt
        ).select_related('vehicle', 'driver')
        
        if not accidents.exists():
            date_range_text = self._format_date_range(start_date, end_date)
            return {
                'message': f"✅ No accidents reported for {date_range_text}.",
                'data': None,
                'data_type': 'text'
            }
        
        table_data = []
        for a in accidents[:10]:
            table_data.append({
                'Date': a.date_time.strftime('%d-%b-%Y'),
                'Vehicle': f"{a.vehicle.make} {a.vehicle.model}" if a.vehicle else 'N/A',
                'Driver': a.driver.get_full_name() if a.driver else 'N/A',
                'Status': a.get_status_display() if hasattr(a, 'get_status_display') else 'Reported'
            })
        
        date_range_text = self._format_date_range(start_date, end_date)
        return {
            'message': f"⚠️ Accidents for {date_range_text}: {accidents.count()} reported",
            'data': table_data,
            'data_type': 'table'
        }
    
    def _get_top_drivers(self, query):
        """Get top drivers by KMs driven."""
        start_date, end_date = self._get_date_range(query)
        start_dt, end_dt = self._get_datetime_range(start_date, end_date)
        
        # Get completed trips
        trips = Trip.objects.filter(
            status='completed',
            is_deleted=False,
            start_time__gte=start_dt,
            start_time__lte=end_dt,
            end_odometer__isnull=False
        ).select_related('driver')
        
        # Calculate KMs per driver
        driver_kms = {}
        for trip in trips:
            driver = trip.driver
            kms = trip.end_odometer - trip.start_odometer
            if driver.id in driver_kms:
                driver_kms[driver.id]['kms'] += kms
                driver_kms[driver.id]['trips'] += 1
            else:
                driver_kms[driver.id] = {
                    'name': driver.get_full_name(),
                    'kms': kms,
                    'trips': 1
                }
        
        if not driver_kms:
            return {
                'message': "No trip data available for ranking.",
                'data': None,
                'data_type': 'text'
            }
        
        # Sort by KMs and get top 10
        sorted_drivers = sorted(driver_kms.values(), key=lambda x: x['kms'], reverse=True)[:10]
        
        table_data = []
        for i, data in enumerate(sorted_drivers, 1):
            medal = '🥇' if i == 1 else ('🥈' if i == 2 else ('🥉' if i == 3 else f'{i}.'))
            table_data.append({
                'Rank': medal,
                'Driver': data['name'],
                'KMs': f"{data['kms']:,} km",
                'Trips': data['trips']
            })
        
        date_range_text = self._format_date_range(start_date, end_date)
        return {
            'message': f"🏆 Top Drivers for {date_range_text}",
            'data': table_data,
            'data_type': 'table'
        }
    
    def _get_vehicle_usage(self, query):
        """Get vehicle usage statistics."""
        start_date, end_date = self._get_date_range(query)
        start_dt, end_dt = self._get_datetime_range(start_date, end_date)
        
        # Get trips per vehicle
        trips = Trip.objects.filter(
            is_deleted=False,
            start_time__gte=start_dt,
            start_time__lte=end_dt
        ).select_related('vehicle')
        
        vehicle_usage = {}
        for trip in trips:
            v = trip.vehicle
            kms = 0
            if trip.status == 'completed' and trip.end_odometer and trip.start_odometer:
                kms = trip.end_odometer - trip.start_odometer
            
            if v.id in vehicle_usage:
                vehicle_usage[v.id]['trips'] += 1
                vehicle_usage[v.id]['kms'] += kms
            else:
                vehicle_usage[v.id] = {
                    'name': f"{v.make} {v.model}",
                    'plate': v.license_plate,
                    'trips': 1,
                    'kms': kms
                }
        
        if not vehicle_usage:
            return {
                'message': "No vehicle usage data available.",
                'data': None,
                'data_type': 'text'
            }
        
        # Sort by trips and get top 10
        sorted_vehicles = sorted(vehicle_usage.values(), key=lambda x: x['trips'], reverse=True)[:10]
        
        table_data = []
        for data in sorted_vehicles:
            table_data.append({
                'Vehicle': data['name'],
                'Plate': data['plate'],
                'Trips': data['trips'],
                'KMs': f"{data['kms']:,} km"
            })
        
        date_range_text = self._format_date_range(start_date, end_date)
        return {
            'message': f"📊 Most Used Vehicles for {date_range_text}",
            'data': table_data,
            'data_type': 'table'
        }
    
    def _get_sor_high_value(self, query):
        """Get high value SOR entries."""
        start_date, end_date = self._get_date_range(query)
        start_dt, end_dt = self._get_datetime_range(start_date, end_date)
        
        # Get SOR entries ordered by goods value (highest first)
        sor_entries = SOR.objects.filter(
            created_at__gte=start_dt,
            created_at__lte=end_dt
        ).select_related('vehicle', 'driver').order_by('-goods_value')[:15]
        
        if not sor_entries.exists():
            date_range_text = self._format_date_range(start_date, end_date)
            return {
                'message': f"📋 No SOR entries found for {date_range_text}.",
                'data': None,
                'data_type': 'text'
            }
        
        table_data = []
        total_value = 0
        for sor in sor_entries:
            goods_val = float(sor.goods_value) if sor.goods_value else 0
            total_value += goods_val
            
            table_data.append({
                'SOR #': f"#{sor.id}",
                'Goods Value': f"₹{goods_val:,.0f}",
                'Route': f"{sor.from_location[:12]} → {sor.to_location[:12]}",
                'Vehicle': f"{sor.vehicle.make} {sor.vehicle.model}"[:15] if sor.vehicle else 'N/A',
                'Driver': sor.driver.get_full_name()[:15] if sor.driver else 'N/A',
                'Status': sor.get_status_display()
            })
        
        date_range_text = self._format_date_range(start_date, end_date)
        count = sor_entries.count()
        
        return {
            'message': f"💰 High Value SOR Entries for {date_range_text}\n\n📊 Showing Top {count} entries by goods value\n💵 Total Value: ₹{total_value:,.0f}",
            'data': table_data,
            'data_type': 'table'
        }
    
    def _get_sor_status(self, query):
        """Get SOR status summary."""
        start_date, end_date = self._get_date_range(query)
        start_dt, end_dt = self._get_datetime_range(start_date, end_date)
        
        # Get SOR entries for the period
        sor_entries = SOR.objects.filter(
            created_at__gte=start_dt,
            created_at__lte=end_dt
        )
        
        if not sor_entries.exists():
            date_range_text = self._format_date_range(start_date, end_date)
            return {
                'message': f"📋 No SOR entries found for {date_range_text}.",
                'data': None,
                'data_type': 'text'
            }
        
        # Count by status
        total = sor_entries.count()
        pending = sor_entries.filter(status='pending').count()
        driver_accepted = sor_entries.filter(status='driver_accepted').count()
        in_progress = sor_entries.filter(status='in_progress').count()
        completed = sor_entries.filter(status='completed').count()
        rejected = sor_entries.filter(status='rejected').count()
        
        # Total goods value
        total_value = sor_entries.aggregate(total=Sum('goods_value'))['total'] or 0
        
        table_data = [
            {'Status': '📋 Total SOR', 'Count': total, 'Value': f"₹{float(total_value):,.0f}"},
            {'Status': '⏳ Pending', 'Count': pending, 'Value': '-'},
            {'Status': '✅ Driver Accepted', 'Count': driver_accepted, 'Value': '-'},
            {'Status': '🚗 In Progress', 'Count': in_progress, 'Value': '-'},
            {'Status': '✔️ Completed', 'Count': completed, 'Value': '-'},
            {'Status': '❌ Rejected', 'Count': rejected, 'Value': '-'},
        ]
        
        date_range_text = self._format_date_range(start_date, end_date)
        
        return {
            'message': f"📊 SOR Status Summary for {date_range_text}",
            'data': table_data,
            'data_type': 'table'
        }
    
    def _get_help(self):
        """Return help message with available commands."""
        help_items = [
            {'Category': '📏 Distance', 'Example Query': '"Show me driver KMs today"'},
            {'Category': '📏 Distance', 'Example Query': '"Driver KMs for 19/08/2025"'},
            {'Category': '🚗 Vehicles', 'Example Query': '"Vehicle status summary"'},
            {'Category': '🚗 Vehicles', 'Example Query': '"List all available vehicles"'},
            {'Category': '� Vehicles', 'Example Query': '"Count of vehicle types"'},
            {'Category': '�🛣️ Trips', 'Example Query': '"Show ongoing trips"'},
            {'Category': '🛣️ Trips', 'Example Query': '"Completed trips today"'},
            {'Category': '⛽ Fuel', 'Example Query': '"Fuel consumption this week"'},
            {'Category': '⛽ Fuel', 'Example Query': '"Suspicious fuel entries in October"'},
            {'Category': '🔧 Maintenance', 'Example Query': '"Pending maintenance"'},
            {'Category': '👥 Drivers', 'Example Query': '"List all drivers"'},
            {'Category': '🏆 Rankings', 'Example Query': '"Top drivers this month"'},
            {'Category': '📊 Usage', 'Example Query': '"Most used vehicles"'},
            {'Category': '⚠️ Accidents', 'Example Query': '"Accidents this month"'},
            {'Category': '📦 SOR', 'Example Query': '"High value SOR"'},
            {'Category': '📦 SOR', 'Example Query': '"SOR status summary"'},
            {'Category': '📅 Dates', 'Example Query': '"You can use: today, yesterday, week, month, or specific dates like 19/08/2025"'},
        ]
        
        return {
            'message': "🤖 VMS Chatbot Help\n\nHere are some things you can ask me:",
            'data': help_items,
            'data_type': 'table'
        }
    
    def _get_default_response(self):
        """Return default response for unrecognized queries."""
        return {
            'message': "🤔 I'm not sure what you're looking for. Try asking about:\n\n"
                      "• Driver KMs (e.g., 'Show driver KMs today')\n"
                      "• Vehicle status (e.g., 'Vehicle status summary')\n"
                      "• Ongoing trips (e.g., 'Show ongoing trips')\n"
                      "• Fuel consumption (e.g., 'Fuel usage this week')\n"
                      "• Maintenance (e.g., 'Pending maintenance')\n\n"
                      "Type 'help' for more options.",
            'data': None,
            'data_type': 'text'
        }
    
    def _get_smart_response(self, query):
        """Use Groq AI to generate a helpful response for unknown queries."""
        if not self.groq_client:
            return self._get_default_response()
        
        try:
            # Get some context data
            vehicle_count = Vehicle.objects.count()
            driver_count = CustomUser.objects.filter(user_type='driver', is_active=True).count()
            ongoing_trips = Trip.objects.filter(status='ongoing', is_deleted=False).count()
            
            system_prompt = f"""You are a helpful assistant for a Vehicle Management System (VMS).
The system currently has:
- {vehicle_count} vehicles
- {driver_count} active drivers
- {ongoing_trips} ongoing trips

The user asked something you can't directly answer with data. Provide a helpful response that:
1. Acknowledges their question
2. Suggests related queries they could ask
3. Keep it brief and friendly (2-3 sentences max)

Available data queries:
- Driver kilometers/distance
- Vehicle status/list
- Ongoing trips
- Fuel consumption
- Maintenance schedules
- Accident reports
- Driver rankings"""

            response = self.groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=0.7,
                max_tokens=150
            )
            
            ai_response = response.choices[0].message.content.strip()
            return {
                'message': f"🤖 {ai_response}",
                'data': None,
                'data_type': 'text'
            }
        except Exception as e:
            print(f"Groq error: {e}")
            return self._get_default_response()
    
    def _format_date_range(self, start_date, end_date):
        """Format date range for display."""
        if start_date == end_date:
            if start_date == self.today:
                return "Today"
            elif start_date == self.today - timedelta(days=1):
                return "Yesterday"
            else:
                return start_date.strftime('%d %b %Y')
        else:
            return f"{start_date.strftime('%d %b')} - {end_date.strftime('%d %b %Y')}"
