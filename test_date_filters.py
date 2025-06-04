#!/usr/bin/env python
"""
Test script to verify date filtering fixes in ManualTripListView
"""
import os
import sys
import django
from datetime import datetime, timedelta

# Set up Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vehicle_management.settings')
django.setup()

# Import models and Django utilities after setup
from django.utils import timezone
from django.db.models import Q
from trips.models import Trip
from django.http import HttpRequest
from django.contrib.auth import get_user_model

User = get_user_model()

def simulate_request(params=None):
    """Create a simulated request with GET parameters"""
    request = HttpRequest()
    request.GET = params or {}
    request.user = User.objects.filter(user_type__in=['admin', 'manager']).first()
    if not request.user:
        print("Warning: No admin/manager user found. Creating a test user.")
        request.user = User.objects.create(
            username="test_admin",
            email="test@example.com",
            user_type="admin"
        )
    return request

def simulate_view_queryset(request):
    """Simulate the exact filtering logic from ManualTripListView.get_queryset()"""
    queryset = Trip.objects.all().select_related('vehicle', 'driver').order_by('-start_time')

    search = request.GET.get('search', '').strip()
    if search:
        queryset = queryset.filter(
            Q(vehicle__license_plate__icontains=search) |
            Q(driver__first_name__icontains=search) |
            Q(driver__last_name__icontains=search) |
            Q(origin__icontains=search) |
            Q(destination__icontains=search) |
            Q(purpose__icontains=search)
        )

    # Date filtering logic (fixed version)
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if date_from and date_to:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            
            # If same day, use exact date match instead of range
            if date_from_obj == date_to_obj:
                queryset = queryset.filter(start_time__date=date_from_obj)
            else:
                queryset = queryset.filter(
                    start_time__date__gte=date_from_obj,
                    start_time__date__lte=date_to_obj
                )
        except ValueError:
            print(f"Invalid date format: date_from={date_from}, date_to={date_to}")
    elif date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            queryset = queryset.filter(start_time__date__gte=date_from_obj)
        except ValueError:
            print(f"Invalid date_from: {date_from}")
    elif date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            queryset = queryset.filter(start_time__date__lte=date_to_obj)
        except ValueError:
            print(f"Invalid date_to: {date_to}")

    status = request.GET.get('status')
    if status:
        queryset = queryset.filter(status=status)

    driver_id = request.GET.get('driver')
    if driver_id and driver_id.isdigit():
        queryset = queryset.filter(driver_id=int(driver_id))

    vehicle_id = request.GET.get('vehicle')
    if vehicle_id and vehicle_id.isdigit():
        queryset = queryset.filter(vehicle_id=int(vehicle_id))

    return queryset

def test_today_filter():
    """Test the 'Today' filter"""
    today = timezone.now().date()
    today_str = today.strftime('%Y-%m-%d')
    
    # Create request with Today filter
    params = {'date_from': today_str, 'date_to': today_str, 'date_filter': 'today'}
    request = simulate_request(params)
    
    # Get filtered queryset
    queryset = simulate_view_queryset(request)
    
    # Count trips with direct date filter for comparison
    direct_filter = Trip.objects.filter(start_time__date=today)
    
    print(f"\n--- Testing Today Filter ({today_str}) ---")
    print(f"Trips found with view logic: {queryset.count()}")
    print(f"Trips found with direct filter: {direct_filter.count()}")
    print(f"Test passed: {queryset.count() == direct_filter.count()}")
    
    # Print sample trips for debugging
    print("\nSample trips found:")
    for trip in queryset[:3]:
        print(f"  Trip {trip.id}: {trip.start_time} (date: {trip.start_time.date()})")
    
    return queryset.count() == direct_filter.count()

def test_this_week_filter():
    """Test the 'This Week' filter"""
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    # Create request with This Week filter
    params = {
        'date_from': start_of_week.strftime('%Y-%m-%d'), 
        'date_to': end_of_week.strftime('%Y-%m-%d'),
        'date_filter': 'week'
    }
    request = simulate_request(params)
    
    # Get filtered queryset
    queryset = simulate_view_queryset(request)
    
    # Count trips with direct date filter for comparison
    direct_filter = Trip.objects.filter(
        start_time__date__gte=start_of_week,
        start_time__date__lte=end_of_week
    )
    
    print(f"\n--- Testing This Week Filter ({start_of_week} to {end_of_week}) ---")
    print(f"Trips found with view logic: {queryset.count()}")
    print(f"Trips found with direct filter: {direct_filter.count()}")
    print(f"Test passed: {queryset.count() == direct_filter.count()}")
    
    # Print sample trips for debugging
    print("\nSample trips found:")
    for trip in queryset[:3]:
        print(f"  Trip {trip.id}: {trip.start_time} (date: {trip.start_time.date()})")
    
    return queryset.count() == direct_filter.count()

def test_this_month_filter():
    """Test the 'This Month' filter"""
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    # Get last day of month
    if today.month == 12:
        end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    
    # Create request with This Month filter
    params = {
        'date_from': start_of_month.strftime('%Y-%m-%d'), 
        'date_to': end_of_month.strftime('%Y-%m-%d'),
        'date_filter': 'month'
    }
    request = simulate_request(params)
    
    # Get filtered queryset
    queryset = simulate_view_queryset(request)
    
    # Count trips with direct date filter for comparison
    direct_filter = Trip.objects.filter(
        start_time__date__gte=start_of_month,
        start_time__date__lte=end_of_month
    )
    
    print(f"\n--- Testing This Month Filter ({start_of_month} to {end_of_month}) ---")
    print(f"Trips found with view logic: {queryset.count()}")
    print(f"Trips found with direct filter: {direct_filter.count()}")
    print(f"Test passed: {queryset.count() == direct_filter.count()}")
    
    # Print sample trips for debugging
    print("\nSample trips found:")
    for trip in queryset[:3]:
        print(f"  Trip {trip.id}: {trip.start_time} (date: {trip.start_time.date()})")
    
    return queryset.count() == direct_filter.count()

def test_custom_date_range():
    """Test a custom date range filter"""
    today = timezone.now().date()
    date_from = today - timedelta(days=7)
    date_to = today
    
    # Create request with custom date range
    params = {
        'date_from': date_from.strftime('%Y-%m-%d'), 
        'date_to': date_to.strftime('%Y-%m-%d'),
        'date_filter': 'custom'
    }
    request = simulate_request(params)
    
    # Get filtered queryset
    queryset = simulate_view_queryset(request)
    
    # Count trips with direct date filter for comparison
    direct_filter = Trip.objects.filter(
        start_time__date__gte=date_from,
        start_time__date__lte=date_to
    )
    
    print(f"\n--- Testing Custom Date Range ({date_from} to {date_to}) ---")
    print(f"Trips found with view logic: {queryset.count()}")
    print(f"Trips found with direct filter: {direct_filter.count()}")
    print(f"Test passed: {queryset.count() == direct_filter.count()}")
    
    # Print sample trips for debugging
    print("\nSample trips found:")
    for trip in queryset[:3]:
        print(f"  Trip {trip.id}: {trip.start_time} (date: {trip.start_time.date()})")
    
    return queryset.count() == direct_filter.count()

def test_same_day_date_range():
    """Test a same-day date range (the case that was fixed)"""
    # Find a date with trips for testing
    today = timezone.now().date()
    
    # Try to find a day with trips, starting from today and going back up to 7 days
    test_date = today
    for i in range(7):
        if Trip.objects.filter(start_time__date=test_date).exists():
            break
        test_date = today - timedelta(days=i+1)
    
    # Create request with same-day date range
    params = {
        'date_from': test_date.strftime('%Y-%m-%d'), 
        'date_to': test_date.strftime('%Y-%m-%d'),
        'date_filter': 'custom'
    }
    request = simulate_request(params)
    
    # Get filtered queryset
    queryset = simulate_view_queryset(request)
    
    # Count trips with direct date filter for comparison
    direct_filter = Trip.objects.filter(start_time__date=test_date)
    
    print(f"\n--- Testing Same-Day Date Range ({test_date}) ---")
    print(f"Trips found with view logic: {queryset.count()}")
    print(f"Trips found with direct filter: {direct_filter.count()}")
    print(f"Test passed: {queryset.count() == direct_filter.count()}")
    
    # Print sample trips for debugging
    print("\nSample trips found:")
    for trip in queryset[:3]:
        print(f"  Trip {trip.id}: {trip.start_time} (date: {trip.start_time.date()})")
    
    return queryset.count() == direct_filter.count()

def display_trip_data():
    """Display general trip data for debugging"""
    all_trips = Trip.objects.all()
    
    print("\n--- Trip Data Overview ---")
    print(f"Total trips in database: {all_trips.count()}")
    
    # Get date range of trips
    if all_trips.exists():
        earliest = all_trips.order_by('start_time').first().start_time
        latest = all_trips.order_by('-start_time').first().start_time
        print(f"Date range: {earliest.date()} to {latest.date()}")
    
    # Count trips by date
    today = timezone.now().date()
    today_trips = Trip.objects.filter(start_time__date=today)
    print(f"Trips today ({today}): {today_trips.count()}")
    
    # Count trips this week
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    week_trips = Trip.objects.filter(
        start_time__date__gte=start_of_week,
        start_time__date__lte=end_of_week
    )
    print(f"Trips this week ({start_of_week} to {end_of_week}): {week_trips.count()}")
    
    # Count trips this month
    start_of_month = today.replace(day=1)
    if today.month == 12:
        end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    month_trips = Trip.objects.filter(
        start_time__date__gte=start_of_month,
        start_time__date__lte=end_of_month
    )
    print(f"Trips this month ({start_of_month} to {end_of_month}): {month_trips.count()}")

def run_tests():
    """Run all tests and display results"""
    print("=== Testing Date Filtering Logic in ManualTripListView ===")
    
    # Display general trip data
    display_trip_data()
    
    # Run tests
    today_test = test_today_filter()
    week_test = test_this_week_filter()
    month_test = test_this_month_filter()
    custom_test = test_custom_date_range()
    same_day_test = test_same_day_date_range()
    
    # Display summary
    print("\n=== Test Results Summary ===")
    print(f"Today filter test: {'PASSED' if today_test else 'FAILED'}")
    print(f"This Week filter test: {'PASSED' if week_test else 'FAILED'}")
    print(f"This Month filter test: {'PASSED' if month_test else 'FAILED'}")
    print(f"Custom Date Range test: {'PASSED' if custom_test else 'FAILED'}")
    print(f"Same-Day Date Range test: {'PASSED' if same_day_test else 'FAILED'}")
    
    all_passed = all([today_test, week_test, month_test, custom_test, same_day_test])
    print(f"\nOverall result: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    
    return all_passed

if __name__ == "__main__":
    run_tests()
