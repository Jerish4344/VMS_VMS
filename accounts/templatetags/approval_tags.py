from django import template
from django.utils import timezone
from datetime import timedelta

register = template.Library()

@register.filter
def time_since_request(hr_authenticated_at):
    """Calculate time since HR authentication"""
    if not hr_authenticated_at:
        return "Unknown"
    
    now = timezone.now()
    diff = now - hr_authenticated_at
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "Just now"

@register.filter
def is_urgent_request(hr_authenticated_at):
    """Check if request is urgent (older than 24 hours)"""
    if not hr_authenticated_at:
        return False
    
    twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
    return hr_authenticated_at < twenty_four_hours_ago

@register.simple_tag
def get_employee_hr_role(employee):
    """Get formatted HR role for employee with proper name handling"""
    if not employee.hr_data and not employee.hr_designation:
        return "Employee"
    
    role_parts = []
    
    # Try to get designation/job title from multiple possible fields
    designation = (
        employee.hr_designation or 
        (employee.hr_data.get('designation', '') if employee.hr_data else '') or 
        (employee.hr_data.get('job_title', '') if employee.hr_data else '') or
        (employee.hr_data.get('role', '') if employee.hr_data else '') or
        (employee.hr_data.get('position', '') if employee.hr_data else '') or
        (employee.hr_data.get('title', '') if employee.hr_data else '')
    )
    
    # Try to get department from multiple possible fields
    department = (
        employee.hr_department or
        (employee.hr_data.get('department', '') if employee.hr_data else '') or
        (employee.hr_data.get('dept', '') if employee.hr_data else '') or
        (employee.hr_data.get('dept_name', '') if employee.hr_data else '') or
        (employee.hr_data.get('division', '') if employee.hr_data else '')
    )
    
    if designation:
        role_parts.append(designation)
    
    if department:
        role_parts.append(f"({department})")
    
    return " ".join(role_parts) if role_parts else "Employee"

@register.simple_tag  
def get_employee_display_name(employee):
    """Get best available display name for employee with extensive field checking"""
    
    # First try to get the full name from Django model
    if employee.first_name and employee.last_name:
        return f"{employee.first_name} {employee.last_name}"
    elif employee.first_name:
        return employee.first_name
    
    # Try to get name from HR data if Django model doesn't have it
    if employee.hr_data:
        # Try separate first/last name fields with various possible names
        first_name_fields = ['first_name', 'fname', 'firstName', 'given_name']
        last_name_fields = ['last_name', 'lname', 'lastName', 'surname', 'family_name']
        
        hr_first = ''
        hr_last = ''
        
        for field in first_name_fields:
            if employee.hr_data.get(field):
                hr_first = employee.hr_data.get(field)
                break
        
        for field in last_name_fields:
            if employee.hr_data.get(field):
                hr_last = employee.hr_data.get(field)
                break
        
        if hr_first and hr_last:
            return f"{hr_first} {hr_last}"
        elif hr_first:
            return hr_first
        
        # Try full name fields with various possible names
        full_name_fields = ['full_name', 'name', 'display_name', 'employee_name', 'username']
        
        for field in full_name_fields:
            full_name = employee.hr_data.get(field, '')
            if full_name and full_name != employee.username:  # Don't use if it's just the username/ID
                # Check if it looks like an actual name (contains letters and possibly spaces)
                if any(c.isalpha() for c in str(full_name)) and not str(full_name).isdigit():
                    return full_name
    
    # Fallback to username or employee ID, but try to make it more readable
    fallback_name = employee.username or employee.hr_employee_id or "Employee"
    
    # If fallback looks like an ID number, prefix it with "Employee"  
    if str(fallback_name).isdigit():
        return f"Employee {fallback_name}"
    
    return fallback_name

@register.simple_tag
def debug_employee_data(employee):
    """Debug tag to show all available employee data - remove in production"""
    debug_info = {
        'username': employee.username,
        'first_name': employee.first_name,
        'last_name': employee.last_name,
        'hr_employee_id': employee.hr_employee_id,
        'hr_data_keys': list(employee.hr_data.keys()) if employee.hr_data else [],
        'hr_data': employee.hr_data
    }
    return debug_info