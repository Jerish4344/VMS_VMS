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
    # Only show SORs created by the user unless privileged
    privileged_types = ['admin', 'manager', 'vehicle_manager']  # 'sor_team' removed
    if hasattr(request.user, 'user_type') and request.user.user_type in privileged_types:
        sors = SOR.objects.all().order_by('-created_at')
    else:
        sors = SOR.objects.filter(created_by=request.user).order_by('-created_at')
    return render(request, 'sor/sor_list.html', {'sors': sors})

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
