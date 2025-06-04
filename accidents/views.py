# accidents/views.py

from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect
from django.http import HttpResponseRedirect
from django.db.models import Q
from accounts.permissions import AdminRequiredMixin, ManagerRequiredMixin, VehicleManagerRequiredMixin
from .models import Accident, AccidentImage
from vehicles.models import Vehicle
from trips.models import Trip
from .forms import AccidentForm, AccidentUpdateForm, AccidentImageFormSet

class AccidentListView(LoginRequiredMixin, ListView):
    model = Accident
    template_name = 'accidents/accident_list.html'
    context_object_name = 'accidents'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('vehicle', 'driver')
        
        # Search functionality
        search_query = self.request.GET.get('search', None)
        if search_query:
            queryset = queryset.filter(
                Q(vehicle__license_plate__icontains=search_query) |
                Q(driver__first_name__icontains=search_query) |
                Q(driver__last_name__icontains=search_query) |
                Q(location__icontains=search_query) |
                Q(police_report_number__icontains=search_query)
            )
            
        # Filter by vehicle
        vehicle_filter = self.request.GET.get('vehicle', None)
        if vehicle_filter:
            queryset = queryset.filter(vehicle_id=vehicle_filter)
            
        # Filter by status
        status_filter = self.request.GET.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        # Filter by date range
        start_date = self.request.GET.get('start_date', None)
        end_date = self.request.GET.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(date_time__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date_time__date__lte=end_date)
            
        # Filter by driver (if user is a driver)
        if self.request.user.user_type == 'driver':
            queryset = queryset.filter(driver=self.request.user)
            
        # Default ordering
        return queryset.order_by('-date_time')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['vehicles'] = Vehicle.objects.all().order_by('license_plate')
        context['statuses'] = dict(Accident.STATUS_CHOICES)
        
        # Get status counts
        for status, _ in Accident.STATUS_CHOICES:
            context[f'{status}_count'] = Accident.objects.filter(status=status).count()
            
        return context

class AccidentDetailView(LoginRequiredMixin, DetailView):
    model = Accident
    template_name = 'accidents/accident_detail.html'
    context_object_name = 'accident'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add related accidents for the same vehicle
        context['related_accidents'] = Accident.objects.filter(
            vehicle=self.object.vehicle
        ).exclude(id=self.object.id).order_by('-date_time')[:5]
        
        # Get accident images
        context['images'] = self.object.images.all()
        
        return context

class AccidentCreateView(LoginRequiredMixin, CreateView):
    model = Accident
    form_class = AccidentForm
    template_name = 'accidents/accident_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_initial(self):
        initial = super().get_initial()
        
        # If creating from a trip, pre-populate with trip data
        trip_id = self.request.GET.get('trip', None)
        if trip_id:
            try:
                trip = Trip.objects.get(pk=trip_id)
                initial['vehicle'] = trip.vehicle.id
                initial['driver'] = trip.driver.id
            except Trip.DoesNotExist:
                pass
                
        # Pre-populate driver if user is a driver
        if self.request.user.user_type == 'driver':
            initial['driver'] = self.request.user.id
            
            # Pre-populate vehicle if driver has an active trip
            active_trip = Trip.objects.filter(
                driver=self.request.user,
                status='ongoing'
            ).first()
            
            if active_trip:
                initial['vehicle'] = active_trip.vehicle.id
                
        return initial
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.POST:
            context['image_formset'] = AccidentImageFormSet(
                self.request.POST,
                self.request.FILES
            )
        else:
            context['image_formset'] = AccidentImageFormSet()
            
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        image_formset = context['image_formset']
        
        if image_formset.is_valid():
            self.object = form.save()
            
            # Set the vehicle status to 'maintenance' if it's currently in use
            vehicle = self.object.vehicle
            if vehicle.status == 'in_use':
                vehicle.status = 'maintenance'
                vehicle.save()
            
            # Save the accident images
            image_formset.instance = self.object
            image_formset.save()
                
            messages.success(self.request, 'Accident reported successfully.')
            return HttpResponseRedirect(self.get_success_url())
        else:
            return self.form_invalid(form)
            
    def get_success_url(self):
        return reverse_lazy('accident_detail', kwargs={'pk': self.object.pk})

class AccidentUpdateView(VehicleManagerRequiredMixin, UpdateView):
    model = Accident
    form_class = AccidentUpdateForm
    template_name = 'accidents/accident_update_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.POST:
            context['image_formset'] = AccidentImageFormSet(
                self.request.POST,
                self.request.FILES,
                instance=self.object
            )
        else:
            context['image_formset'] = AccidentImageFormSet(instance=self.object)
            
        # Get current images
        context['current_images'] = self.object.images.all()
            
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        image_formset = context['image_formset']
        
        if image_formset.is_valid():
            self.object = form.save()
            
            # Handle status changes affecting vehicle
            old_status = form.initial.get('status')
            new_status = form.cleaned_data.get('status')
            
            if old_status != new_status:
                vehicle = self.object.vehicle
                
                if new_status == 'resolved' and vehicle.status == 'maintenance':
                    # If accident is resolved, set vehicle to available
                    vehicle.status = 'available'
                    vehicle.save()
                elif new_status in ['repair_scheduled', 'repair_in_progress'] and vehicle.status != 'maintenance':
                    # If accident is being repaired, set vehicle to maintenance
                    vehicle.status = 'maintenance'
                    vehicle.save()
            
            # Save the accident images
            image_formset.save()
                
            messages.success(self.request, 'Accident updated successfully.')
            return HttpResponseRedirect(self.get_success_url())
        else:
            return self.form_invalid(form)
            
    def get_success_url(self):
        return reverse_lazy('accident_detail', kwargs={'pk': self.object.pk})

class AccidentDeleteView(AdminRequiredMixin, DeleteView):
    model = Accident
    template_name = 'accidents/accident_confirm_delete.html'
    success_url = reverse_lazy('accident_list')
    
    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        messages.success(self.request, 'Accident record deleted successfully.')
        return response

class RemoveAccidentImageView(VehicleManagerRequiredMixin, DeleteView):
    model = AccidentImage
    
    def get_success_url(self):
        accident_id = self.request.GET.get('accident_id')
        return reverse_lazy('accident_update', kwargs={'pk': accident_id})
    
    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)