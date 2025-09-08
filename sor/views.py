from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages

from .models import SOR
from .forms import SORForm
from .notification import SORNotification
from django.contrib.auth import get_user_model
from trips.models import Trip
from vehicles.models import Vehicle
from django.utils import timezone
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
    sors = SOR.objects.all().order_by('-created_at')
    return render(request, 'sor/sor_list.html', {'sors': sors})

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
