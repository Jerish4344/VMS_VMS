# fuel/views.py
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Q
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.http import JsonResponse

# Import permissions - adjust these imports based on your accounts app structure
try:
    from accounts.permissions import AdminRequiredMixin, ManagerRequiredMixin, VehicleManagerRequiredMixin
except ImportError:
    # Fallback if permissions don't exist
    class AdminRequiredMixin(LoginRequiredMixin):
        pass
    class ManagerRequiredMixin(LoginRequiredMixin):
        pass
    class VehicleManagerRequiredMixin(LoginRequiredMixin):
        pass

from .models import FuelTransaction, FuelStation
from vehicles.models import Vehicle
from .forms import FuelTransactionForm, FuelStationForm

# Custom permission mixins for fuel transactions
class FuelAdminRequiredMixin(LoginRequiredMixin):
    """
    Mixin to ensure only admin users can access the view.
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if request.user.user_type != 'admin':
            messages.error(request, 'You do not have permission to access this feature.')
            return redirect('fuel_transaction_list')
        
        return super().dispatch(request, *args, **kwargs)

class FuelManagerRequiredMixin(LoginRequiredMixin):
    """
    Mixin to ensure only admin and manager users can access the view.
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if request.user.user_type not in ['admin', 'manager']:
            messages.error(request, 'You do not have permission to access this feature.')
            return redirect('fuel_transaction_list')
        
        return super().dispatch(request, *args, **kwargs)

class FuelTransactionListView(LoginRequiredMixin, ListView):
    model = FuelTransaction
    template_name = 'fuel/fuel_transaction_list.html'
    context_object_name = 'transactions'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('vehicle', 'driver', 'fuel_station')
        
        # Search functionality
        search_query = self.request.GET.get('search', None)
        if search_query:
            queryset = queryset.filter(
                Q(vehicle__license_plate__icontains=search_query) |
                Q(driver__first_name__icontains=search_query) |
                Q(driver__last_name__icontains=search_query) |
                Q(fuel_station__name__icontains=search_query)
            )
            
        # Filter by vehicle
        vehicle_filter = self.request.GET.get('vehicle', None)
        if vehicle_filter:
            queryset = queryset.filter(vehicle_id=vehicle_filter)
            
        # Filter by driver
        driver_filter = self.request.GET.get('driver', None)  
        if driver_filter:
            queryset = queryset.filter(driver_id=driver_filter)
            
        # Filter by fuel station - FIX: Check both 'fuel_station' and 'station' parameters
        fuel_station_filter = self.request.GET.get('fuel_station', None) or self.request.GET.get('station', None)
        if fuel_station_filter:
            queryset = queryset.filter(fuel_station_id=fuel_station_filter)
            
        # Filter by transaction type (fuel vs electric)
        transaction_type_filter = self.request.GET.get('transaction_type', None)
        if transaction_type_filter == 'fuel':
            queryset = queryset.filter(
                Q(vehicle__vehicle_type__category__in=['personal', 'commercial']) |
                Q(fuel_type__isnull=False) & ~Q(fuel_type='Electric')
            )
        elif transaction_type_filter == 'electric':
            queryset = queryset.filter(
                Q(vehicle__vehicle_type__category='electric') |
                Q(fuel_type='Electric')
            )
            
        # Filter by fuel type
        fuel_type_filter = self.request.GET.get('fuel_type', None)
        if fuel_type_filter:
            queryset = queryset.filter(fuel_type=fuel_type_filter)
            
        # Filter by date range
        start_date = self.request.GET.get('start_date', None)
        end_date = self.request.GET.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
            
        # Default ordering
        return queryset.order_by('-date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['vehicles'] = Vehicle.objects.all().order_by('license_plate')
        context['fuel_types'] = FuelTransaction.objects.values_list('fuel_type', flat=True).distinct().order_by('fuel_type')
        context['fuel_stations'] = FuelStation.objects.all().order_by('name')  # Add this for filtering
        
        # Get summary data for both fuel and electric vehicles
        queryset = self.get_queryset()
        
        # Calculate aggregates
        aggregates = queryset.aggregate(
            total_quantity=Sum('quantity'),
            total_energy=Sum('energy_consumed'),
            total_cost=Sum('total_cost')
        )
        
        summary = {
            'total_quantity': aggregates['total_quantity'] or 0,
            'total_energy': aggregates['total_energy'] or 0,
            'total_cost': aggregates['total_cost'] or 0,
        }
            
        context['summary'] = summary
        
        # Add selected filters to context for display
        context['selected_fuel_station'] = self.request.GET.get('fuel_station', None) or self.request.GET.get('station', None)
        if context['selected_fuel_station']:
            try:
                context['selected_fuel_station_obj'] = FuelStation.objects.get(id=context['selected_fuel_station'])
            except FuelStation.DoesNotExist:
                context['selected_fuel_station_obj'] = None
        
        return context

class FuelTransactionDetailView(LoginRequiredMixin, DetailView):
    model = FuelTransaction
    template_name = 'fuel/fuel_transaction_detail.html'
    context_object_name = 'transaction'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get previous and next transactions for the same vehicle
        vehicle = self.object.vehicle
        previous_transactions = FuelTransaction.objects.filter(
            vehicle=vehicle,
            date__lt=self.object.date
        ).order_by('-date')[:5]
        
        next_transactions = FuelTransaction.objects.filter(
            vehicle=vehicle,
            date__gt=self.object.date
        ).order_by('date')[:5]
        
        context['previous_transactions'] = previous_transactions
        context['next_transactions'] = next_transactions
        
        # Calculate efficiency if possible
        if previous_transactions.exists():
            previous_transaction = previous_transactions.first()
            distance = self.object.odometer_reading - previous_transaction.odometer_reading
            if distance > 0:
                if hasattr(self.object.vehicle, 'is_electric') and self.object.vehicle.is_electric() and self.object.energy_consumed:
                    # km/kWh for electric vehicles
                    context['efficiency'] = round(distance / float(self.object.energy_consumed), 2)
                    context['efficiency_unit'] = 'km/kWh'
                    context['efficiency_label'] = 'Energy Efficiency'
                elif not (hasattr(self.object.vehicle, 'is_electric') and self.object.vehicle.is_electric()) and self.object.quantity:
                    # km/L for fuel vehicles
                    context['efficiency'] = round(distance / float(self.object.quantity), 2)
                    context['efficiency_unit'] = 'km/L'
                    context['efficiency_label'] = 'Fuel Efficiency'
                
                context['distance_since_last'] = distance
        
        return context

class FuelTransactionCreateView(VehicleManagerRequiredMixin, CreateView):
    model = FuelTransaction
    form_class = FuelTransactionForm
    template_name = 'fuel/fuel_transaction_form.html'
    success_url = reverse_lazy('fuel_transaction_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        try:
            # Set the driver to the current user if they're a driver
            if hasattr(self.request.user, 'user_type') and self.request.user.user_type == 'driver':
                form.instance.driver = self.request.user
                
            # Update vehicle's current odometer if this is newer
            vehicle = form.instance.vehicle
            if vehicle and hasattr(vehicle, 'current_odometer') and form.instance.odometer_reading > vehicle.current_odometer:
                vehicle.current_odometer = form.instance.odometer_reading
                vehicle.save()
            
            response = super().form_valid(form)
            
            # Success message based on vehicle type
            if hasattr(form.instance.vehicle, 'is_electric') and form.instance.vehicle.is_electric():
                messages.success(self.request, 'Charging session added successfully.')
            else:
                messages.success(self.request, 'Fuel transaction added successfully.')
            
            return response
            
        except Exception as e:
            print(f"Error in form_valid: {e}")
            messages.error(self.request, f'Error saving transaction: {str(e)}')
            return self.form_invalid(form)

    def form_invalid(self, form):
        print("Form is invalid!")
        print("Form errors:", form.errors)
        print("Non-field errors:", form.non_field_errors)
        
        # Add error messages for user
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        
        return super().form_invalid(form)

class FuelTransactionUpdateView(FuelManagerRequiredMixin, UpdateView):
    model = FuelTransaction
    form_class = FuelTransactionForm
    template_name = 'fuel/fuel_transaction_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_success_url(self):
        return reverse_lazy('fuel_transaction_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Success message based on vehicle type
        if hasattr(form.instance.vehicle, 'is_electric') and form.instance.vehicle.is_electric():
            messages.success(self.request, 'Charging session updated successfully.')
        else:
            messages.success(self.request, 'Fuel transaction updated successfully.')
            
        return response

class FuelTransactionDeleteView(FuelAdminRequiredMixin, DeleteView):
    model = FuelTransaction
    template_name = 'fuel/fuel_transaction_confirm_delete.html'
    success_url = reverse_lazy('fuel_transaction_list')
    
    def delete(self, request, *args, **kwargs):
        transaction = self.get_object()
        transaction_type = "Charging session" if (hasattr(transaction.vehicle, 'is_electric') and transaction.vehicle.is_electric()) else "Fuel transaction"
        
        response = super().delete(request, *args, **kwargs)
        messages.success(self.request, f'{transaction_type} deleted successfully.')
        return response

# Function-based view for AJAX delete (similar to trip delete)
@login_required
@require_http_methods(["DELETE", "POST"])
def fuel_transaction_delete(request, pk):
    """Delete a fuel transaction"""
    transaction = get_object_or_404(FuelTransaction, pk=pk)
    
    # Check permissions - only admins can delete fuel transactions
    if request.user.user_type != 'admin':
        messages.error(request, "You don't have permission to delete this transaction.")
        return redirect('fuel_transaction_detail', pk=transaction.pk)
    
    # Store transaction info for the success message before deletion
    transaction_type = "Charging session" if (hasattr(transaction.vehicle, 'is_electric') and transaction.vehicle.is_electric()) else "Fuel transaction"
    transaction_info = f"{transaction_type} for {transaction.vehicle.license_plate} on {transaction.date}"
    
    if request.method == 'DELETE' or request.method == 'POST':
        try:
            # Delete the transaction
            transaction.delete()
            
            # Handle different response types
            if request.headers.get('Content-Type') == 'application/json' or request.META.get('HTTP_ACCEPT', '').startswith('application/json'):
                return JsonResponse({'status': 'success', 'message': f'{transaction_info} deleted successfully!'})
            else:
                messages.success(request, f'{transaction_info} deleted successfully!')
                return redirect('fuel_transaction_list')
                
        except Exception as e:
            error_msg = f'Error deleting transaction: {str(e)}'
            if request.headers.get('Content-Type') == 'application/json' or request.META.get('HTTP_ACCEPT', '').startswith('application/json'):
                return JsonResponse({'status': 'error', 'message': error_msg})
            else:
                messages.error(request, error_msg)
                return redirect('fuel_transaction_detail', pk=pk)
    
    # If GET request, redirect to transaction detail
    return redirect('fuel_transaction_detail', pk=pk)

# Fuel Station Views
class FuelStationListView(LoginRequiredMixin, ListView):
    model = FuelStation
    template_name = 'fuel/fuel_station_list.html'
    context_object_name = 'stations'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Add search functionality
        search_query = self.request.GET.get('search', None)
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(address__icontains=search_query)
            )
        
        return queryset.order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add transaction counts for each station
        stations = context['stations']
        for station in stations:
            station.transaction_count = FuelTransaction.objects.filter(fuel_station=station).count()
            
        return context

class FuelStationCreateView(VehicleManagerRequiredMixin, CreateView):
    model = FuelStation
    form_class = FuelStationForm
    template_name = 'fuel/fuel_station_form.html'
    success_url = reverse_lazy('fuel_station_list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        station_type = form.instance.get_station_type_display()
        messages.success(self.request, f'{station_type} added successfully.')
        return response

class FuelStationUpdateView(VehicleManagerRequiredMixin, UpdateView):
    model = FuelStation
    form_class = FuelStationForm
    template_name = 'fuel/fuel_station_form.html'
    success_url = reverse_lazy('fuel_station_list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        station_type = form.instance.get_station_type_display()
        messages.success(self.request, f'{station_type} updated successfully.')
        return response

class FuelStationDeleteView(FuelAdminRequiredMixin, DeleteView):
    model = FuelStation
    template_name = 'fuel/fuel_station_confirm_delete.html'
    success_url = reverse_lazy('fuel_station_list')
    
    def delete(self, request, *args, **kwargs):
        station = self.get_object()
        station_type = station.get_station_type_display()
        
        response = super().delete(request, *args, **kwargs)
        messages.success(self.request, f'{station_type} deleted successfully.')
        return response