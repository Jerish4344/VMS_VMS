from django.contrib import admin
from .models import Document, DocumentType

@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    """Admin configuration for DocumentType model."""
    
    list_display = ('name', 'description', 'required')
    search_fields = ('name',)
    list_filter = ('required',)

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """Admin configuration for Document model."""
    
    list_display = ('id', 'vehicle', 'document_type', 'document_number', 'issue_date', 'expiry_date', 'is_expired')
    list_filter = ('document_type', 'vehicle')
    search_fields = ('vehicle__license_plate', 'document_type__name', 'document_number')
    fieldsets = (
        ('Document Information', {
            'fields': ('vehicle', 'document_type', 'document_number', 'issuing_authority')
        }),
        ('Validity Period', {
            'fields': ('issue_date', 'expiry_date')
        }),
        ('File', {
            'fields': ('file',)
        }),
        ('Additional Information', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )
    
    def is_expired(self, obj):
        """Check if document is expired."""
        from django.utils import timezone
        return obj.expiry_date < timezone.now().date()
    
    is_expired.boolean = True
    is_expired.short_description = "Expired"