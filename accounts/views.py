# accounts/views.py - Updated login view with better redirect logic
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.urls import reverse_lazy
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, View
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, JsonResponse
from django.contrib.auth import logout
from django.db import models  # Add this import for Q objects
from .models import CustomUser
from .permissions import AdminRequiredMixin, ManagerRequiredMixin, VehicleManagerRequiredMixin
from .forms import ApprovalAuthenticationForm, DriverApprovalForm
from .decorators import approval_required, manager_required, vehicle_manager_required
import logging
from django.views.generic import CreateView, UpdateView, DetailView
from .forms import CustomUserCreationForm, CustomUserChangeForm
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

class ApprovalLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = ApprovalAuthenticationForm
    redirect_authenticated_user = False  # We'll handle redirects manually
    
    def get_success_url(self):
        """
        Redirect users based on their approval status and user type
        """
        user = self.request.user
        
        # For managers/admins - direct access to dashboard
        if user.has_approval_permissions():
            return reverse_lazy('dashboard')
        
        # For employees - check approval status
        if user.user_type == 'driver':
            if user.approval_status == 'pending':
                return reverse_lazy('pending_approval')
            elif user.approval_status == 'rejected':
                return reverse_lazy('access_rejected')
            elif user.approval_status == 'approved':
                return reverse_lazy('dashboard')
            else:
                # Fallback for any other status
                return reverse_lazy('pending_approval')
        
        # Fallback
        return reverse_lazy('dashboard')
    
    def form_valid(self, form):
        """Handle successful login with appropriate messages"""
        user = form.get_user()
        
        # Log successful authentication
        auth_type = "StyleHR" if user.user_type == 'driver' else "Local"
        logger.info(f"User {user.username} authenticated via {auth_type}")
        
        # Handle different user states with appropriate messages
        if user.user_type == 'driver':
            if user.approval_status == 'pending':
                messages.info(
                    self.request,
                    f'Welcome {user.get_full_name()}! Your vehicle access request is pending approval from management. '
                    f'You will be notified once your request is reviewed.'
                )
            elif user.approval_status == 'rejected':
                messages.error(
                    self.request,
                    f'Hello {user.get_full_name()}, your vehicle access request has been rejected. '
                    f'Please contact management for more information.'
                )
            elif user.approval_status == 'approved':
                hr_role = user.get_hr_role_display()
                messages.success(
                    self.request,
                    f'Welcome back, {user.get_full_name()} ({hr_role})! '
                    f'You have full access to the vehicle management system.'
                )
        else:
            # Managers/Vehicle Managers/Admins
            user_type_display = {
                'admin': 'Administrator',
                'manager': 'Manager', 
                'vehicle_manager': 'Vehicle Manager'
            }.get(user.user_type, 'Manager')
            
            messages.success(
                self.request,
                f'Welcome back, {user.get_full_name()}! You have full {user_type_display.lower()} access.'
            )
        
        return super().form_valid(form)
    
    def dispatch(self, request, *args, **kwargs):
        """
        Handle already authenticated users
        """
        if request.user.is_authenticated:
            # Redirect authenticated users based on their status
            if request.user.has_approval_permissions():
                return redirect('dashboard')
            elif request.user.user_type == 'driver':
                if not request.user.can_access_system():
                    if request.user.approval_status == 'pending':
                        return redirect('pending_approval')
                    elif request.user.approval_status == 'rejected':
                        return redirect('access_rejected')
                else:
                    return redirect('dashboard')
        
        return super().dispatch(request, *args, **kwargs)


def custom_logout(request):
    """Custom logout function"""
    user_name = request.user.get_full_name() if request.user.is_authenticated else "User"
    logout(request)
    messages.success(request, f'Goodbye {user_name}! You have been successfully logged out.')
    return redirect('login')


@login_required
def pending_approval_view(request):
    """View for employees pending approval - blocks all other access"""
    # Only allow drivers with pending status
    if request.user.user_type != 'driver' or request.user.approval_status != 'pending':
        if request.user.has_approval_permissions():
            return redirect('dashboard')
        elif request.user.approval_status == 'approved':
            return redirect('dashboard')
        elif request.user.approval_status == 'rejected':
            return redirect('access_rejected')
        else:
            # Fallback to logout if something is wrong
            messages.error(request, 'There was an issue with your account status. Please login again.')
            return redirect('logout')
    
    context = {
        'user': request.user,
        'hr_data': request.user.hr_data or {},
        'authenticated_at': request.user.hr_authenticated_at,
        'hr_role': request.user.get_hr_role_display(),
    }
    return render(request, 'accounts/pending_approval.html', context)


@login_required
def access_rejected_view(request):
    """View for employees with rejected access - blocks all other access"""
    # Only allow drivers with rejected status
    if request.user.user_type != 'driver' or request.user.approval_status != 'rejected':
        if request.user.has_approval_permissions():
            return redirect('dashboard')
        elif request.user.approval_status == 'approved':
            return redirect('dashboard')
        elif request.user.approval_status == 'pending':
            return redirect('pending_approval')
        else:
            # Fallback to logout if something is wrong
            messages.error(request, 'There was an issue with your account status. Please login again.')
            return redirect('logout')
    
    context = {
        'user': request.user,
        'rejection_reason': request.user.rejection_reason,
        'rejected_by': request.user.approved_by,
        'rejected_at': request.user.approved_at,
        'hr_role': request.user.get_hr_role_display(),
    }
    return render(request, 'accounts/access_rejected.html', context)


# Manager-only views (unchanged but with explicit decorator)
@vehicle_manager_required
def pending_employees_list_view(request):
    """List view for pending employee approvals"""
    model = CustomUser
    template_name = 'accounts/pending_employees.html'
    context_object_name = 'pending_employees'
    # Use the class-based view logic
    view = PendingEmployeesListView.as_view()
    return view(request)

class PendingEmployeesListView(VehicleManagerRequiredMixin, ListView):
    """List view for pending employee approvals"""
    model = CustomUser
    template_name = 'accounts/pending_employees.html'
    context_object_name = 'pending_employees'
    
    def get_queryset(self):
        return CustomUser.objects.filter(
            user_type='driver',
            approval_status='pending'
        ).order_by('-hr_authenticated_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['approved_employees'] = CustomUser.objects.filter(
            user_type='driver',
            approval_status='approved'
        ).count()
        context['rejected_employees'] = CustomUser.objects.filter(
            user_type='driver',
            approval_status='rejected'
        ).count()
        return context


class EmployeeApprovalView(VehicleManagerRequiredMixin, View):
    """View to approve or reject employee access"""
    
    def get(self, request, employee_id):
        employee = get_object_or_404(
            CustomUser, 
            id=employee_id, 
            user_type='driver',
            approval_status='pending'
        )
        
        context = {
            'employee': employee,
            'hr_data': employee.hr_data or {},
            'form': DriverApprovalForm()
        }
        return render(request, 'accounts/employee_approval.html', context)
    
    def post(self, request, employee_id):
        employee = get_object_or_404(
            CustomUser, 
            id=employee_id, 
            user_type='driver',
            approval_status='pending'
        )
        
        action = request.POST.get('action')
        
        if action == 'approve':
            employee.approve_access(request.user)
            messages.success(
                request,
                f'Employee {employee.get_full_name()} has been approved for vehicle system access.'
            )
            logger.info(f"Employee {employee.username} approved by {request.user.username}")
            
        elif action == 'reject':
            reason = request.POST.get('rejection_reason', '')
            employee.reject_access(request.user, reason)
            messages.warning(
                request,
                f'Employee {employee.get_full_name()} access has been rejected.'
            )
            logger.info(f"Employee {employee.username} rejected by {request.user.username}")
        
        return redirect('pending_employees')


class AllEmployeesListView(VehicleManagerRequiredMixin, ListView):
    """List all employees with their approval status"""
    model = CustomUser
    template_name = 'accounts/all_employees.html'
    context_object_name = 'employees'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = CustomUser.objects.filter(user_type='driver').order_by('-hr_authenticated_at')
        
        # Filter by status if requested
        status = self.request.GET.get('status')
        if status in ['pending', 'approved', 'rejected']:
            queryset = queryset.filter(approval_status=status)
        
        # Filter by department if requested
        department = self.request.GET.get('department')
        if department:
            queryset = queryset.filter(hr_department__icontains=department)
        
        # Search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(first_name__icontains=search) |
                models.Q(last_name__icontains=search) |
                models.Q(email__icontains=search) |
                models.Q(username__icontains=search) |
                models.Q(hr_employee_id__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', '')
        context['department_filter'] = self.request.GET.get('department', '')
        context['total_employees'] = CustomUser.objects.filter(user_type='driver').count()
        context['pending_count'] = CustomUser.objects.filter(
            user_type='driver', approval_status='pending'
        ).count()
        context['approved_count'] = CustomUser.objects.filter(
            user_type='driver', approval_status='approved'
        ).count()
        context['rejected_count'] = CustomUser.objects.filter(
            user_type='driver', approval_status='rejected'
        ).count()
        
        # Get unique departments for filter
        context['departments'] = CustomUser.objects.filter(
            user_type='driver', 
            hr_department__isnull=False
        ).exclude(hr_department='').values_list('hr_department', flat=True).distinct()
        
        return context


@vehicle_manager_required
def toggle_employee_status(request, employee_id):
    """AJAX view to quickly approve/reject employees"""
    if request.method == 'POST':
        employee = get_object_or_404(CustomUser, id=employee_id, user_type='driver')
        action = request.POST.get('action')
        
        if action == 'approve':
            employee.approve_access(request.user)
            return JsonResponse({
                'success': True,
                'message': f'{employee.get_full_name()} approved',
                'new_status': 'approved'
            })
        
        elif action == 'reject':
            reason = request.POST.get('reason', 'No reason provided')
            employee.reject_access(request.user, reason)
            return JsonResponse({
                'success': True,
                'message': f'{employee.get_full_name()} rejected',
                'new_status': 'rejected'
            })
        
        elif action == 'reset':
            employee.approval_status = 'pending'
            employee.approved_by = None
            employee.approved_at = None
            employee.rejection_reason = ''
            employee.save()
            return JsonResponse({
                'success': True,
                'message': f'{employee.get_full_name()} reset to pending',
                'new_status': 'pending'
            })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@vehicle_manager_required
def get_notification_data(request):
    """AJAX endpoint to get notification data"""
    from django.utils import timezone
    from datetime import timedelta
    
    # Get pending approvals
    pending_employees = CustomUser.objects.filter(
        user_type='driver',
        approval_status='pending'
    ).order_by('-hr_authenticated_at')[:10]
    
    # Format data for JSON response
    notifications = []
    for employee in pending_employees:
        # Calculate urgency
        is_urgent = False
        time_text = "Just now"
        
        if employee.hr_authenticated_at:
            diff = timezone.now() - employee.hr_authenticated_at
            if diff.days > 1:
                is_urgent = True
                time_text = f"{diff.days} days ago"
            elif diff.days == 1:
                is_urgent = True
                time_text = "1 day ago"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                if hours > 8:
                    is_urgent = True
                time_text = f"{hours} hours ago"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                time_text = f"{minutes} minutes ago"
        
        # Get HR role - try multiple field names from StyleHR
        hr_role = "Employee"
        if employee.hr_designation:
            hr_role = employee.hr_designation
            if employee.hr_department:
                hr_role += f" ({employee.hr_department})"
        elif employee.hr_data:
            # Try different possible field names from StyleHR API
            designation = (
                employee.hr_data.get('designation', '') or
                employee.hr_data.get('job_title', '') or
                employee.hr_data.get('role', '') or
                employee.hr_data.get('position', '')
            )
            department = (
                employee.hr_data.get('department', '') or
                employee.hr_data.get('dept', '') or
                employee.hr_data.get('dept_name', '')
            )
            
            if designation:
                hr_role = designation
                if department:
                    hr_role += f" ({department})"
            elif department:
                hr_role = f"Employee ({department})"
        
        # Get display name - try multiple sources
        display_name = employee.get_full_name()
        if not display_name or display_name == employee.username:
            # Try to get name from HR data
            if employee.hr_data:
                hr_first = employee.hr_data.get('first_name', '') or employee.hr_data.get('fname', '')
                hr_last = employee.hr_data.get('last_name', '') or employee.hr_data.get('lname', '')
                
                if hr_first and hr_last:
                    display_name = f"{hr_first} {hr_last}"
                elif hr_first:
                    display_name = hr_first
                else:
                    # Try full name field
                    full_name = employee.hr_data.get('full_name', '') or employee.hr_data.get('name', '')
                    if full_name:
                        display_name = full_name
        
        # Fallback to username if still no name
        if not display_name:
            display_name = employee.username
        
        notifications.append({
            'id': employee.id,
            'name': display_name,
            'hr_role': hr_role,
            'employee_id': employee.hr_employee_id,
            'time_text': time_text,
            'is_urgent': is_urgent,
            'avatar_url': employee.profile_picture.url if employee.profile_picture else None,
            'avatar_initial': display_name[0] if display_name else 'E'
        })
    
    return JsonResponse({
        'notifications': notifications,
        'total_count': len(notifications),
        'has_urgent': any(n['is_urgent'] for n in notifications)
    })


# Keep legacy names for backward compatibility
PendingDriversListView = PendingEmployeesListView
DriverApprovalView = EmployeeApprovalView
AllDriversListView = AllEmployeesListView
toggle_driver_status = toggle_employee_status

# Keep existing admin views (unchanged)

class UserListView(AdminRequiredMixin, ListView):
    model = CustomUser
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    paginate_by = 20  # Add pagination
    
    def get_queryset(self):
        queryset = CustomUser.objects.all().order_by('-date_joined')
        
        # Search filter
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(username__icontains=search) |
                Q(email__icontains=search)
            )
        
        # User type filter
        user_types = self.request.GET.getlist('user_type')
        if user_types:
            queryset = queryset.filter(user_type__in=user_types)
        
        # Status filter
        statuses = self.request.GET.getlist('status')
        if statuses:
            if 'active' in statuses and 'inactive' in statuses:
                pass  # Show all
            elif 'active' in statuses:
                queryset = queryset.filter(is_active=True)
            elif 'inactive' in statuses:
                queryset = queryset.filter(is_active=False)
        
        # License filter (for drivers)
        license_filters = self.request.GET.getlist('license')
        if license_filters:
            license_q = Q()
            
            if 'valid' in license_filters:
                # Valid license: license_expiry is in the future and user is driver
                license_q |= Q(
                    user_type='driver',
                    license_expiry__gt=timezone.now().date()
                )
            
            if 'expired' in license_filters:
                # Expired license: license_expiry is in the past and user is driver
                license_q |= Q(
                    user_type='driver',
                    license_expiry__lt=timezone.now().date()
                )
            
            if 'expiring_soon' in license_filters:
                # Expiring soon: license expires within 30 days
                thirty_days_from_now = timezone.now().date() + timedelta(days=30)
                license_q |= Q(
                    user_type='driver',
                    license_expiry__gt=timezone.now().date(),
                    license_expiry__lte=thirty_days_from_now
                )
            
            queryset = queryset.filter(license_q)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Calculate user type counts from all users (not just filtered results)
        user_counts = CustomUser.objects.values('user_type').annotate(
            count=Count('id')
        )
        
        # Initialize counts
        admin_count = 0
        manager_count = 0
        vehicle_manager_count = 0
        driver_count = 0
        
        # Populate counts from query results
        for item in user_counts:
            user_type = item['user_type']
            count = item['count']
            
            if user_type == 'admin':
                admin_count = count
            elif user_type == 'manager':
                manager_count = count
            elif user_type == 'vehicle_manager':
                vehicle_manager_count = count
            elif user_type == 'driver':
                driver_count = count
        
        # Add counts to context for the dashboard cards
        context.update({
            'admin_count': admin_count,
            'manager_count': manager_count,
            'vehicle_manager_count': vehicle_manager_count,
            'driver_count': driver_count,
            'total_users': CustomUser.objects.count(),
            'active_users': CustomUser.objects.filter(is_active=True).count(),
            'inactive_users': CustomUser.objects.filter(is_active=False).count(),
        })
        
        # Add current time for license expiry calculations
        context['now'] = timezone.now()
        
        # Add debug info
        context['debug_counts'] = {
            'total_users_in_db': CustomUser.objects.count(),
            'filtered_users_count': self.get_queryset().count(),
            'user_type_breakdown': list(user_counts)
        }
        
        return context

class UserCreateView(AdminRequiredMixin, CreateView):
    model = CustomUser
    form_class = CustomUserCreationForm
    template_name = 'accounts/user_form.html'
    success_url = reverse_lazy('user_list')

class UserUpdateView(AdminRequiredMixin, UpdateView):
    model = CustomUser
    form_class = CustomUserChangeForm
    template_name = 'accounts/user_form.html'
    success_url = reverse_lazy('user_list')

class UserDetailView(AdminRequiredMixin, DetailView):
    model = CustomUser
    template_name = 'accounts/user_detail.html'
    context_object_name = 'user_profile'

class UserDeactivateView(AdminRequiredMixin, View):
    def post(self, request, pk):
        user = CustomUser.objects.get(pk=pk)
        user.is_active = False
        user.save()
        messages.success(request, f'User {user.get_full_name()} has been deactivated.')
        return HttpResponseRedirect(reverse_lazy('user_list'))

class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    form_class = CustomUserChangeForm
    template_name = 'accounts/profile_form.html'
    success_url = reverse_lazy('profile')
    
    def get_object(self, queryset=None):
        return self.request.user
