from django.urls import path
from .views import (
    ApprovalLoginView, pending_approval_view, access_rejected_view,
    PendingEmployeesListView, EmployeeApprovalView, AllEmployeesListView,
    toggle_employee_status, custom_logout, get_notification_data,
    # Keep legacy names for backward compatibility
    PendingDriversListView, DriverApprovalView, AllDriversListView, toggle_driver_status,
    # Existing admin views
    UserListView, UserCreateView, UserUpdateView, UserDetailView, 
    UserDeactivateView, ProfileUpdateView,
    # Generator user management views
    GeneratorUserApprovalView, GeneratorUserManagementView, StoreAccessManagementView
)

urlpatterns = [
    # Authentication URLs
    path('login/', ApprovalLoginView.as_view(), name='login'),
    path('logout/', custom_logout, name='logout'),
    
    # Notification URLs
    path('notifications/data/', get_notification_data, name='notification_data'),
    
    # Employee approval system URLs (new)
    path('pending-approval/', pending_approval_view, name='pending_approval'),
    path('access-rejected/', access_rejected_view, name='access_rejected'),
    path('pending-employees/', PendingEmployeesListView.as_view(), name='pending_employees'),
    path('all-employees/', AllEmployeesListView.as_view(), name='all_employees'),
    path('employees/<int:employee_id>/approve/', EmployeeApprovalView.as_view(), name='employee_approval'),
    path('employees/<int:employee_id>/toggle-status/', toggle_employee_status, name='toggle_employee_status'),
    
    # Legacy driver URLs (backward compatibility - same views, different names)
    path('pending-drivers/', PendingDriversListView.as_view(), name='pending_drivers'),
    path('all-drivers/', AllDriversListView.as_view(), name='all_drivers'),
    path('drivers/<int:driver_id>/approve/', DriverApprovalView.as_view(), name='driver_approval'),
    path('drivers/<int:driver_id>/toggle-status/', toggle_driver_status, name='toggle_driver_status'),
    
    # Admin user management URLs (existing)
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/add/', UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/edit/', UserUpdateView.as_view(), name='user_update'),
    path('users/<int:pk>/', UserDetailView.as_view(), name='user_detail'),
    path('users/<int:pk>/deactivate/', UserDeactivateView.as_view(), name='user_deactivate'),
    
    # Profile management
    path('profile/', ProfileUpdateView.as_view(), name='profile'),
    
    # Generator user management URLs
    path('generator-users/', GeneratorUserManagementView.as_view(), name='generator_user_management'),
    path('generator-users/<int:employee_id>/approve/', GeneratorUserApprovalView.as_view(), name='generator_user_approval'),
    path('store-access-management/', StoreAccessManagementView.as_view(), name='store_access_management'),
]
