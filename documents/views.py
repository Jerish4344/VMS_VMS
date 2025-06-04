# documents/views.py
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from accounts.permissions import AdminRequiredMixin, ManagerRequiredMixin, VehicleManagerRequiredMixin
from .models import Document, DocumentType
from vehicles.models import Vehicle
from .forms import DocumentForm, DocumentTypeForm

class DocumentListView(LoginRequiredMixin, ListView):
    model = Document
    template_name = 'documents/document_list.html'
    context_object_name = 'documents'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('vehicle', 'document_type')
        
        # Search functionality
        search_query = self.request.GET.get('search', None)
        if search_query:
            queryset = queryset.filter(
                Q(vehicle__license_plate__icontains=search_query) |
                Q(document_type__name__icontains=search_query) |
                Q(document_number__icontains=search_query) |
                Q(issuing_authority__icontains=search_query)
            )
            
        # Filter by vehicle
        vehicle_filter = self.request.GET.get('vehicle', None)
        if vehicle_filter:
            queryset = queryset.filter(vehicle_id=vehicle_filter)
            
        # Filter by document type
        document_type_filter = self.request.GET.get('document_type', None)
        if document_type_filter:
            queryset = queryset.filter(document_type_id=document_type_filter)
            
        # Filter by expiry status
        expiry_filter = self.request.GET.get('expiry', None)
        today = timezone.now().date()
        
        if expiry_filter == 'expired':
            queryset = queryset.filter(expiry_date__lt=today)
        elif expiry_filter == 'expiring_soon':
            # Documents expiring in the next 30 days
            thirty_days_later = today + timezone.timedelta(days=30)
            queryset = queryset.filter(expiry_date__range=[today, thirty_days_later])
        elif expiry_filter == 'valid':
            queryset = queryset.filter(expiry_date__gt=today)
            
        # Default ordering
        return queryset.order_by('expiry_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['vehicles'] = Vehicle.objects.all().order_by('license_plate')
        context['document_types'] = DocumentType.objects.all().order_by('name')
        
        # Get counts for different expiry statuses
        today = timezone.now().date()
        thirty_days_later = today + timezone.timedelta(days=30)
        
        # Get exact counts to ensure accuracy
        context['expired_count'] = Document.objects.filter(expiry_date__lt=today).count()
        context['expiring_soon_count'] = Document.objects.filter(
            expiry_date__range=[today, thirty_days_later]
        ).count()
        context['valid_count'] = Document.objects.filter(expiry_date__gt=thirty_days_later).count()
        
        return context

class DocumentDetailView(LoginRequiredMixin, DetailView):
    model = Document
    template_name = 'documents/document_detail.html'
    context_object_name = 'document'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get other documents for the same vehicle
        vehicle = self.object.vehicle
        context['related_documents'] = Document.objects.filter(
            vehicle=vehicle
        ).exclude(id=self.object.id).order_by('expiry_date')
        
        # Check if document is expired
        today = timezone.now().date()
        context['is_expired'] = self.object.expiry_date < today
        
        # If expired, calculate days since expiry
        if context['is_expired']:
            context['days_expired'] = (today - self.object.expiry_date).days
        else:
            # If not expired, calculate days until expiry
            context['days_until_expiry'] = (self.object.expiry_date - today).days
            
        return context

class DocumentCreateView(VehicleManagerRequiredMixin, CreateView):
    model = Document
    form_class = DocumentForm
    template_name = 'documents/document_form.html'
    success_url = reverse_lazy('document_list')
    
    def get_initial(self):
        initial = super().get_initial()
        # Pre-populate vehicle if provided in URL
        vehicle_id = self.request.GET.get('vehicle', None)
        if vehicle_id:
            initial['vehicle'] = vehicle_id
        return initial
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Document added successfully.')
        return response

class DocumentUpdateView(VehicleManagerRequiredMixin, UpdateView):
    model = Document
    form_class = DocumentForm
    template_name = 'documents/document_form.html'
    
    def get_success_url(self):
        return reverse_lazy('document_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Document updated successfully.')
        return response

class DocumentDeleteView(AdminRequiredMixin, DeleteView):
    model = Document
    template_name = 'documents/document_confirm_delete.html'
    success_url = reverse_lazy('document_list')
    
    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        messages.success(self.request, 'Document deleted successfully.')
        return response

# Document Type Views
class DocumentTypeListView(VehicleManagerRequiredMixin, ListView):
    model = DocumentType
    template_name = 'documents/document_type_list.html'
    context_object_name = 'document_types'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # The document_count property already exists - no need to set it
        # It will be calculated automatically when accessed in the template
        
        return context

class DocumentTypeCreateView(VehicleManagerRequiredMixin, CreateView):
    model = DocumentType
    form_class = DocumentTypeForm
    template_name = 'documents/document_type_form.html'
    success_url = reverse_lazy('document_type_list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Document type added successfully.')
        return response

class DocumentTypeUpdateView(VehicleManagerRequiredMixin, UpdateView):
    model = DocumentType
    form_class = DocumentTypeForm
    template_name = 'documents/document_type_form.html'
    success_url = reverse_lazy('document_type_list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Document type updated successfully.')
        return response

class DocumentTypeDeleteView(AdminRequiredMixin, DeleteView):
    model = DocumentType
    template_name = 'documents/document_type_confirm_delete.html'
    success_url = reverse_lazy('document_type_list')
    
    def delete(self, request, *args, **kwargs):
        # Check if there are any documents using this type
        doc_type = self.get_object()
        if Document.objects.filter(document_type=doc_type).exists():
            messages.error(
                self.request,
                'Cannot delete document type because it is being used by existing documents.'
            )
            return self.get(request, *args, **kwargs)
        
        response = super().delete(request, *args, **kwargs)
        messages.success(self.request, 'Document type deleted successfully.')
        return response

# documents/forms.py
from django import forms
from .models import Document, DocumentType
from django.conf import settings
import os

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = [
            'vehicle', 'document_type', 'document_number', 'issue_date',
            'expiry_date', 'issuing_authority', 'file', 'notes'
        ]
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Check file size
            if file.size > settings.MAX_DOCUMENT_SIZE:
                max_size_mb = settings.MAX_DOCUMENT_SIZE / (1024 * 1024)
                raise forms.ValidationError(f'File size exceeds the maximum allowed size ({max_size_mb} MB).')
            
            # Check file extension
            ext = os.path.splitext(file.name)[1].lower()[1:]
            allowed_extensions = settings.ALLOWED_DOCUMENT_TYPES
            if ext not in allowed_extensions:
                raise forms.ValidationError(
                    f'File type not supported. Allowed types: {", ".join(allowed_extensions)}'
                )
        return file
    
    def clean(self):
        cleaned_data = super().clean()
        issue_date = cleaned_data.get('issue_date')
        expiry_date = cleaned_data.get('expiry_date')
        
        if issue_date and expiry_date and issue_date > expiry_date:
            self.add_error('expiry_date', 'Expiry date cannot be earlier than issue date.')
            
        return cleaned_data

class DocumentTypeForm(forms.ModelForm):
    class Meta:
        model = DocumentType
        fields = ['name', 'description', 'required']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }