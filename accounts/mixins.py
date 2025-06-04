from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect
from django.contrib import messages

class ApprovalRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        if self.request.user.has_approval_permissions():
            return True
        return self.request.user.can_access_system()
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            if self.request.user.approval_status == 'pending':
                messages.warning(self.request, 'Your account is pending approval.')
                return redirect('pending_approval')
            elif self.request.user.approval_status == 'rejected':
                messages.error(self.request, 'Your access has been rejected.')
                return redirect('access_rejected')
        return super().handle_no_permission()

class EmployeeRequiredMixin(ApprovalRequiredMixin):
    def test_func(self):
        if not super().test_func():
            return False
        return self.request.user.user_type == 'driver'
    
