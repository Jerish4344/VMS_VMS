# Parse Seating# vehicles/utils.py
import pandas as pd
import numpy as np
from django.utils import timezone
from datetime import datetime
import re
from django.db import transaction
from .models import Vehicle, VehicleType
from documents.models import Document

def import_vehicles_from_excel(file_path):
    """
    Import vehicles from Excel file and create associated documents.
    
    Args:
        file_path: Path to Excel file or a file-like object
    
    Returns:
        dict: Results with success_count, error_count, errors
    """
    try:
        # Read Excel file
        df = pd.read_excel(file_path)
        
        # Clean column names (remove extra spaces and normalize)
        df.columns = [col.strip() if isinstance(col, str) else col for col in df.columns]
        
        # Create column mapping for your Excel file
        column_mapping = {
            'Sl No': 'sl_no',
            'Vehicles No.': 'license_plate', 
            'Type': 'vehicle_type',
            'Vehicle make & Model': 'make_model',
            'Year of Manufacture': 'year',
            'Vehicle Capacity': 'seating_capacity',
            'Fuel Type': 'fuel_type',
            'Fuel Capacity': 'fuel_capacity', 
            'Average Mileage': 'average_mileage',
            'Owner Name': 'owner_name',
            'RC Valid Till': 'rc_valid_till',
            'Insurance Expiry Date': 'insurance_expiry_date',
            'Fitness Expiry': 'fitness_expiry',
            'Permit Expiry': 'permit_expiry',
            'Pollution Cert Expiry': 'pollution_cert_expiry',
            'GPS Fitted': 'gps_fitted',
            'GPS_Name': 'gps_name',
            'Driver Contact': 'driver_contact',
            'Assigned Driver': 'assigned_driver',
            'CHASSIS NO': 'vin',
            'Remarke': 'remarks',
            'Purpose of vehicle': 'purpose_of_vehicle',
            'Company_Owned': 'company_owned',
            'usage_type': 'usage_type',
            'used by': 'used_by'
        }
        
        # Rename columns to match our expected names
        df = df.rename(columns=column_mapping)
        
        # Fill NaN values with empty strings
        df = df.fillna('')
        
        # Remove rows where license_plate is empty or contains header-like values
        df = df[df['license_plate'].astype(str).str.strip() != '']
        df = df[~df['license_plate'].astype(str).str.contains('Vehicles No', na=False)]
        df = df[df['license_plate'] != 'license_plate']  # Remove any header rows
        
        # Process each row
        success_count = 0
        error_count = 0
        errors = []
        imported_vehicles = []
        
        for index, row in df.iterrows():
            try:
                # Skip empty rows or rows without license plate
                license_plate_raw = row.get('license_plate', '')
                license_plate = str(license_plate_raw).strip() if license_plate_raw is not None else ''
                
                if (not license_plate or 
                    license_plate == '' or 
                    license_plate.lower() in ['nan', 'none', 'null'] or
                    license_plate == 'undefined'):
                    continue
                
                with transaction.atomic():
                    # Check if vehicle already exists
                    existing_vehicle = Vehicle.objects.filter(license_plate=license_plate).first()
                    
                    if existing_vehicle:
                        vehicle = existing_vehicle
                    else:
                        vehicle = Vehicle()
                        vehicle.license_plate = license_plate
                    
                    # Get or create vehicle type (required field)
                    vehicle_type_name = row.get('vehicle_type', '')
                    
                    # Handle various empty/null cases including undefined
                    if (vehicle_type_name is None or 
                        vehicle_type_name == '' or 
                        str(vehicle_type_name).strip().lower() in ['', 'nan', 'none', 'null', 'undefined']):
                        
                        # Try to infer type from make/model if available
                        make_model = str(row.get('make_model', '')).strip()
                        if 'PICKUP' in make_model.upper():
                            vehicle_type_name = 'Pickup Truck'
                            category = 'commercial'
                        elif 'TRUCK' in make_model.upper():
                            vehicle_type_name = 'Truck'
                            category = 'commercial'
                        elif 'VAN' in make_model.upper():
                            vehicle_type_name = 'Van'
                            category = 'commercial'
                        elif 'EV' in make_model.upper() or 'ELECTRIC' in make_model.upper():
                            vehicle_type_name = 'Electric Car'
                            category = 'electric'
                        elif any(word in make_model.upper() for word in ['CAR', 'SEDAN', 'HATCHBACK', 'SUV', 'INNOVA', 'SWIFT', 'BREEZA']):
                            vehicle_type_name = 'Car'
                            category = 'personal'
                        else:
                            vehicle_type_name = 'Unknown'
                            category = 'personal'
                    else:
                        vehicle_type_name = str(vehicle_type_name).strip()
                        # Determine category based on vehicle type name
                        if any(word in vehicle_type_name.upper() for word in ['TRUCK', 'PICKUP', 'VAN', 'LORRY', 'COMMERCIAL']):
                            category = 'commercial'
                        elif any(word in vehicle_type_name.upper() for word in ['EV', 'ELECTRIC', 'HYBRID']):
                            category = 'electric'
                        else:
                            category = 'personal'
                    
                    # Create or get the vehicle type with category
                    vehicle_type, created = VehicleType.objects.get_or_create(
                        name=vehicle_type_name,
                        defaults={
                            'description': f"Imported from Excel - {vehicle_type_name}",
                            'category': category
                        }
                    )
                    vehicle.vehicle_type = vehicle_type
                    
                    # Parse Make & Model
                    make_model = str(row.get('make_model', '')).strip()
                    if make_model and make_model.lower() not in ['', 'nan', 'none']:
                        # For single word makes like "AUDI", "BENZ", set as make
                        parts = make_model.split(' ', 1)
                        vehicle.make = parts[0].strip()
                        vehicle.model = parts[1].strip() if len(parts) > 1 else parts[0].strip()
                    
                    # Parse Year - handle both datetime objects and numbers
                    year_value = row.get('year', '')
                    if year_value and str(year_value).strip().lower() not in ['', 'nan', 'none']:
                        try:
                            if isinstance(year_value, datetime):
                                vehicle.year = year_value.year
                            elif isinstance(year_value, str) and 'T' in year_value:
                                # Handle ISO datetime strings
                                dt = datetime.fromisoformat(year_value.replace('Z', '+00:00'))
                                vehicle.year = dt.year
                            elif isinstance(year_value, (int, float)):
                                vehicle.year = int(year_value)
                            else:
                                # Try to parse as string
                                year_str = str(year_value).strip()
                                if year_str.isdigit():
                                    vehicle.year = int(year_str)
                                else:
                                    vehicle.year = timezone.now().year
                        except (ValueError, TypeError):
                            vehicle.year = timezone.now().year
                    else:
                        vehicle.year = timezone.now().year
                    
                    # Parse Seating Capacity and Load Capacity
                    capacity = row.get('seating_capacity', '')
                    if capacity and str(capacity).strip().lower() not in ['', 'nan', 'none']:
                        try:
                            capacity_val = int(float(str(capacity)))
                            if capacity_val > 0:
                                vehicle.seating_capacity = capacity_val
                        except (ValueError, TypeError):
                            vehicle.seating_capacity = 1  # Default
                    else:
                        vehicle.seating_capacity = 1
                    
                    # Handle load capacity for commercial vehicles
                    load_capacity = row.get('load_capacity_kg', '') or row.get('Load Capacity', '') or row.get('Vehicle Capacity', '')
                    if load_capacity and str(load_capacity).strip().lower() not in ['', 'nan', 'none']:
                        try:
                            # Check if the capacity mentions KG or is a commercial vehicle
                            capacity_str = str(load_capacity).upper()
                            if 'KG' in capacity_str or vehicle.vehicle_type.is_commercial():
                                # Extract numeric value
                                import re
                                number_match = re.search(r'\d+(\.\d+)?', capacity_str)
                                if number_match:
                                    vehicle.load_capacity_kg = float(number_match.group())
                        except (ValueError, TypeError):
                            pass
                    
                    # Set Fuel Type and Electric Vehicle handling
                    fuel_type = str(row.get('fuel_type', '')).strip()
                    if fuel_type and fuel_type.lower() not in ['', 'nan', 'none']:
                        vehicle.fuel_type = fuel_type
                        
                        # Check if it's an electric vehicle
                        if fuel_type.upper() in ['EV', 'ELECTRIC', 'BATTERY']:
                            # Update vehicle type to electric if not already
                            if not vehicle.vehicle_type.is_electric():
                                electric_type, created = VehicleType.objects.get_or_create(
                                    name='Electric Vehicle',
                                    defaults={
                                        'description': 'Electric Vehicle - Auto-detected from fuel type',
                                        'category': 'electric'
                                    }
                                )
                                vehicle.vehicle_type = electric_type
                    else:
                        # Default fuel type based on vehicle type
                        if vehicle.vehicle_type.is_electric():
                            vehicle.fuel_type = 'Electric'
                        else:
                            vehicle.fuel_type = 'Petrol'  # Default
                    
                    # Handle fuel capacity or battery capacity
                    if vehicle.vehicle_type.is_electric():
                        # For electric vehicles, look for battery capacity
                        battery_capacity = row.get('battery_capacity_kwh', '') or row.get('Battery Capacity', '')
                        if battery_capacity and str(battery_capacity).strip().lower() not in ['', 'nan', 'none', 'null']:
                            try:
                                vehicle.battery_capacity_kwh = float(str(battery_capacity))
                            except (ValueError, TypeError):
                                vehicle.battery_capacity_kwh = 50.0  # Default for electric
                        else:
                            vehicle.battery_capacity_kwh = 50.0
                        
                        # Set range per charge
                        range_per_charge = row.get('range_per_charge', '') or row.get('Range', '')
                        if range_per_charge and str(range_per_charge).strip().lower() not in ['', 'nan', 'none', 'null']:
                            try:
                                vehicle.range_per_charge = int(float(str(range_per_charge)))
                            except (ValueError, TypeError):
                                vehicle.range_per_charge = 300  # Default range
                        else:
                            vehicle.range_per_charge = 300
                        
                        # Set charging type
                        charging_type = row.get('charging_type', '') or row.get('Charging Type', '')
                        if charging_type and str(charging_type).strip().lower() not in ['', 'nan', 'none']:
                            vehicle.charging_type = str(charging_type).strip()
                        else:
                            vehicle.charging_type = 'Type 2'  # Default
                        
                        # Clear fuel-specific fields for electric vehicles
                        vehicle.fuel_capacity = None
                        vehicle.average_mileage = None
                    else:
                        # For non-electric vehicles, handle fuel capacity
                        fuel_capacity = row.get('fuel_capacity', '')
                        if fuel_capacity and str(fuel_capacity).strip().lower() not in ['', 'nan', 'none', 'null']:
                            try:
                                vehicle.fuel_capacity = float(str(fuel_capacity))
                            except (ValueError, TypeError):
                                vehicle.fuel_capacity = 50.0  # Default
                        else:
                            vehicle.fuel_capacity = 50.0
                        
                        # Set Average Mileage for fuel vehicles
                        avg_mileage = row.get('average_mileage', '')
                        if avg_mileage and str(avg_mileage).strip().lower() not in ['', 'nan', 'none', 'null']:
                            try:
                                vehicle.average_mileage = float(str(avg_mileage))
                            except (ValueError, TypeError):
                                vehicle.average_mileage = 15.0  # Default
                        else:
                            vehicle.average_mileage = 15.0
                        
                        # Clear electric-specific fields for non-electric vehicles
                        vehicle.battery_capacity_kwh = None
                        vehicle.range_per_charge = None
                        vehicle.charging_type = ''
                        vehicle.charging_time_hours = None
                    
                    # Set Owner Name with length limit
                    owner_name = str(row.get('owner_name', '')).strip()
                    if owner_name and owner_name.lower() not in ['', 'nan', 'none']:
                        # Truncate to fit database field length (150 chars)
                        vehicle.owner_name = owner_name[:150]
                    
                    # Parse dates with improved handling
                    date_fields = {
                        'rc_valid_till': 'rc_valid_till',
                        'insurance_expiry_date': 'insurance_expiry_date', 
                        'fitness_expiry': 'fitness_expiry',
                        'permit_expiry': 'permit_expiry',
                        'pollution_cert_expiry': 'pollution_cert_expiry'
                    }
                    
                    for field_name, model_field in date_fields.items():
                        date_value = row.get(field_name, '')
                        if date_value and str(date_value).strip().lower() not in ['', 'nan', 'none', 'nil']:
                            parsed_date = parse_date_from_excel(date_value)
                            if parsed_date:
                                setattr(vehicle, model_field, parsed_date)
                    
                    # Set GPS Info
                    gps_fitted = str(row.get('gps_fitted', '')).strip().upper()
                    vehicle.gps_fitted = 'yes' if gps_fitted in ['YES', 'Y', '1', 'TRUE'] else 'no'
                    
                    gps_name = str(row.get('gps_name', '')).strip()
                    if gps_name and gps_name.lower() not in ['', 'nan', 'none', 'na']:
                        # Truncate to fit database field length (100 chars)
                        vehicle.gps_name = gps_name[:100]
                    
                    # Set Driver Info with length limits
                    driver_contact = str(row.get('driver_contact', '')).strip()
                    if driver_contact and driver_contact.lower() not in ['', 'nan', 'none', 'self', 'nil']:
                        # Truncate to fit database field length (100 chars)
                        vehicle.driver_contact = driver_contact[:100]
                    
                    assigned_driver = str(row.get('assigned_driver', '')).strip()
                    if assigned_driver and assigned_driver.lower() not in ['', 'nan', 'none', 'nil']:
                        # Truncate to fit database field length (150 chars)
                        vehicle.assigned_driver = assigned_driver[:150]
                    
                    # Set VIN/Chassis Number
                    vin = str(row.get('vin', '')).strip()
                    if vin and vin.lower() not in ['', 'nan', 'none']:
                        vehicle.vin = vin
                    else:
                        # Generate a placeholder VIN if not provided
                        vehicle.vin = f"VIN{license_plate.replace('-', '')}"
                    
                    # Set Purpose and Usage with length limits
                    purpose = str(row.get('purpose_of_vehicle', '')).strip()
                    if purpose and purpose.lower() not in ['', 'nan', 'none']:
                        # Truncate to fit database field length (200 chars)
                        vehicle.purpose_of_vehicle = purpose[:200]
                    
                    company_owned = str(row.get('company_owned', '')).strip().lower()
                    vehicle.company_owned = 'yes' if company_owned in ['yes', 'y', '1', 'true'] else 'no'
                    
                    usage_type = str(row.get('usage_type', '')).strip().lower()
                    if usage_type in ['personal', 'staff', 'other']:
                        vehicle.usage_type = usage_type
                    else:
                        vehicle.usage_type = 'staff'  # Default
                    
                    used_by = str(row.get('used_by', '')).strip()
                    if used_by and used_by.lower() not in ['', 'nan', 'none']:
                        # Truncate to fit database field length (150 chars)
                        vehicle.used_by = used_by[:150]
                    
                    # Set default values for required fields
                    if not vehicle.acquisition_date:
                        vehicle.acquisition_date = timezone.now().date()
                    
                    if not vehicle.status:
                        vehicle.status = 'available'
                    
                    if not vehicle.color:
                        vehicle.color = 'White'
                    
                    if not vehicle.current_odometer:
                        vehicle.current_odometer = 0
                    
                    # Save the vehicle
                    vehicle.save()
                    
                    # Create documents for this vehicle
                    try:
                        Document.create_from_vehicle(vehicle)
                    except Exception as doc_error:
                        # Don't fail the import if document creation fails
                        print(f"Warning: Could not create documents for {license_plate}: {doc_error}")
                    
                    imported_vehicles.append(license_plate)
                    success_count += 1
                    
            except Exception as e:
                error_count += 1
                # Get the license plate for error reporting, handling None/undefined cases
                license_plate_for_error = row.get('license_plate', 'Unknown')
                if license_plate_for_error is None:
                    license_plate_for_error = 'Unknown'
                else:
                    license_plate_for_error = str(license_plate_for_error)
                
                error_msg = f"Row {index+1} (License Plate: {license_plate_for_error}): {str(e)}"
                errors.append(error_msg)
                
                # Add debug info for vehicle type issues
                if 'vehicle_type_id' in str(e):
                    vehicle_type_debug = row.get('vehicle_type', 'NOT_FOUND')
                    make_model_debug = row.get('make_model', 'NOT_FOUND')
                    error_msg += f" [Debug: Type='{vehicle_type_debug}', Make/Model='{make_model_debug}']"
                    errors.append(error_msg)
                
                continue
        
        return {
            'success_count': success_count,
            'error_count': error_count,
            'errors': errors,
            'imported_vehicles': imported_vehicles
        }
        
    except Exception as e:
        return {
            'success_count': 0,
            'error_count': 1,
            'errors': [f"File processing error: {str(e)}"],
            'imported_vehicles': []
        }


def parse_date_from_excel(date_value):
    """
    Parse a date from various formats in Excel with improved handling.
    """
    if pd.isna(date_value) or date_value == '' or str(date_value).strip().lower() in ['nil', 'none', 'nan']:
        return None
    
    # If it's already a datetime
    if isinstance(date_value, (datetime, pd.Timestamp)):
        return date_value.date()
    
    # If it's a string
    if isinstance(date_value, str):
        date_str = date_value.strip()
        
        # Handle ISO format strings
        if 'T' in date_str:
            try:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                return dt.date()
            except:
                pass
        
        # Try different date formats
        date_formats = [
            '%d-%m-%Y',    # 12-11-2025
            '%d/%m/%Y',    # 21/06/2025
            '%m/%d/%Y',    # 06/21/2025
            '%Y-%m-%d',    # 2025-06-21
            '%d-%m-%y',    # 21-06-25
            '%d/%m/%y',    # 21/06/25
            '%m/%d/%y',    # 06/21/25
            '%d.%m.%Y',    # 21.06.2025
            '%m.%d.%Y',    # 06.21.2025
            '%Y.%m.%d',    # 2025.06.21
            '%d.%m.%y',    # 21.06.25
            '%m.%d.%y',    # 06.21.25
            '%b %d, %Y',   # Jun 21, 2025
            '%B %d, %Y',   # June 21, 2025
            '%d %b %Y',    # 21 Jun 2025
            '%d %B %Y',    # 21 June 2025
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
    
    # Try numeric parsing - Excel stores dates as serial numbers
    try:
        number = float(date_value)
        if 30000 < number < 50000:  # Range for reasonable Excel dates
            base_date = datetime(1899, 12, 30)  # Excel's day 0
            delta = pd.Timedelta(days=number)
            return (base_date + delta).date()
    except (ValueError, TypeError, OverflowError):
        pass
    
    return None