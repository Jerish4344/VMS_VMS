from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from datetime import datetime, time
from django.utils import timezone

from .models import SOR
from .forms import SORForm, SORFilterForm
from .notification import SORNotification
from django.contrib.auth import get_user_model
from trips.models import Trip
from vehicles.models import Vehicle
User = get_user_model()

@login_required
def sor_create(request):
    # Allow only users with 'sor.add_sor' permission, managers, or vehicle managers
    user_type = getattr(request.user, 'user_type', None)
    if not (request.user.has_perm('sor.add_sor') or user_type in ['manager', 'vehicle_manager']):
        messages.error(request, 'You do not have permission to create SOR entries.')
        return redirect('sor_list')
    if request.method == 'POST':
        post_data = request.POST.copy()
        # If "Others" is selected, replace with the typed value
        if post_data.get('from_location') == 'Others':
            other = post_data.get('from_location_other', '').strip()
            if other:
                post_data['from_location'] = other
        if post_data.get('to_location') == 'Others':
            other = post_data.get('to_location_other', '').strip()
            if other:
                post_data['to_location'] = other
        form = SORForm(post_data)
        if form.is_valid():
            sor = form.save(commit=False)
            sor.created_by = request.user
            sor.save()
            # Create notification for driver
            SORNotification.objects.create(
                sor=sor,
                driver=sor.driver,
                message=f"You have a new SOR assignment from {sor.from_location} to {sor.to_location}. Please accept or reject.",
            )
            messages.success(request, 'SOR entry created and driver notified.')
            return redirect('sor_list')
    else:
        form = SORForm()
    return render(request, 'sor/sor_form.html', {'form': form})

@login_required
def sor_list(request):
    # Only show SORs created by the user unless privileged
    privileged_types = ['admin', 'manager', 'vehicle_manager']
    if hasattr(request.user, 'user_type') and request.user.user_type in privileged_types:
        sors = SOR.objects.all()
    else:
        sors = SOR.objects.filter(created_by=request.user)
    
    # Initialize filter form
    filter_form = SORFilterForm(request.GET or None)
    
    # Apply filters if form is valid
    if filter_form.is_valid():
        # Search filter
        search = filter_form.cleaned_data.get('search')
        if search:
            sors = sors.filter(
                Q(id__icontains=search) |
                Q(goods_value__icontains=search) |
                Q(from_location__icontains=search) |
                Q(to_location__icontains=search) |
                Q(driver__first_name__icontains=search) |
                Q(driver__last_name__icontains=search) |
                Q(vehicle__license_plate__icontains=search)
            )
        
        # Status filter
        status = filter_form.cleaned_data.get('status')
        if status:
            sors = sors.filter(status=status)
        
        # From location filter
        from_location = filter_form.cleaned_data.get('from_location')
        if from_location:
            sors = sors.filter(from_location=from_location)
        
        # To location filter
        to_location = filter_form.cleaned_data.get('to_location')
        if to_location:
            sors = sors.filter(to_location=to_location)
        
        # Vehicle filter
        vehicle = filter_form.cleaned_data.get('vehicle')
        if vehicle:
            sors = sors.filter(vehicle=vehicle)
        
        # Driver filter
        driver = filter_form.cleaned_data.get('driver')
        if driver:
            sors = sors.filter(driver=driver)
        
        # Date range filters
        date_from = filter_form.cleaned_data.get('date_from')
        if date_from:
            # Filter from start of the selected date
            start_datetime = timezone.make_aware(datetime.combine(date_from, time.min))
            sors = sors.filter(created_at__gte=start_datetime)
        
        date_to = filter_form.cleaned_data.get('date_to')
        if date_to:
            # Filter until end of the selected date
            end_datetime = timezone.make_aware(datetime.combine(date_to, time.max))
            sors = sors.filter(created_at__lte=end_datetime)
    
    # Order by created_at descending
    sors = sors.order_by('-created_at')
    
    # Pagination - 30 items per page
    paginator = Paginator(sors, 30)
    page = request.GET.get('page')
    
    try:
        sors_page = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page
        sors_page = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page
        sors_page = paginator.page(paginator.num_pages)
    
    context = {
        'sors': sors_page,
        'filter_form': filter_form,
        'total_count': paginator.count,
        'has_filters': any(filter_form.cleaned_data.values()) if filter_form.is_valid() else False,
    }
    
    return render(request, 'sor/sor_list.html', context)

# --- SOR View, Edit, Delete Placeholder Views ---
from django.http import HttpResponseForbidden

@login_required
def sor_view(request, pk):
    sor = get_object_or_404(SOR, pk=pk)
    # You can add more permission logic here if needed
    return render(request, 'sor/sor_form.html', {'form': None, 'sor': sor, 'view_only': True})

@login_required
def sor_edit(request, pk):
    sor = get_object_or_404(SOR, pk=pk)
    # Only admin or sor_team can edit
    if request.user.user_type not in ['admin', 'sor_team', 'manager', 'vehicle_manager']:
        return HttpResponseForbidden('You do not have permission to edit this SOR.')
    if request.method == 'POST':
        form = SORForm(request.POST, instance=sor)
        if form.is_valid():
            updated_sor = form.save()
            # Update or create notification for driver
            from .notification import SORNotification
            notif_message = f"SOR assignment updated: {updated_sor.from_location} to {updated_sor.to_location}. Please check details."
            notif_qs = SORNotification.objects.filter(sor=updated_sor, driver=updated_sor.driver, is_read=False).order_by('-created_at')
            if notif_qs.exists():
                notif = notif_qs.first()
                notif.message = notif_message
                notif.save()
            else:
                SORNotification.objects.create(
                    sor=updated_sor,
                    driver=updated_sor.driver,
                    message=notif_message
                )
            messages.success(request, 'SOR entry updated successfully and driver notified.')
            return redirect('sor_list')
    else:
        form = SORForm(instance=sor)
    return render(request, 'sor/sor_form.html', {'form': form, 'sor': sor, 'edit_mode': True})

@login_required
def sor_delete(request, pk):
    sor = get_object_or_404(SOR, pk=pk)
    # Only admin can delete
    if request.user.user_type != 'admin':
        return HttpResponseForbidden('You do not have permission to delete this SOR.')
    if request.method == 'POST':
        sor.delete()
        messages.success(request, 'SOR entry deleted.')
        return redirect('sor_list')
    return render(request, 'sor/sor_confirm_delete.html', {'sor': sor})

@login_required
def sor_accept(request, pk):
    sor = get_object_or_404(SOR, pk=pk, driver=request.user)
    if sor.status == 'pending':
        sor.status = 'driver_accepted'
        sor.save()
        # Start trip automatically
        # Use SOR's from_location, to_location, vehicle, driver, and distance
        start_odometer = sor.vehicle.current_odometer or 0
        trip = Trip.objects.create(
            vehicle=sor.vehicle,
            driver=sor.driver,
            start_time=timezone.now(),
            start_odometer=start_odometer,
            origin=sor.from_location,
            destination=sor.to_location,
            purpose=f"SOR Goods Value: {sor.goods_value}",
            notes=f"Started from SOR entry #{sor.id}",
            status='ongoing',
            entry_type='real_time',
        )
        sor.trip = trip
        sor.status = 'in_progress'
        sor.save()
        # Mark notification as read
        SORNotification.objects.filter(sor=sor, driver=request.user, is_read=False).update(is_read=True)
        messages.success(request, 'SOR accepted and trip started.')
    return redirect('sor_list')
