// static/js/main.js

/**
 * Main JavaScript file for the Vehicle Management System
 */

document.addEventListener('DOMContentLoaded', function() {
  // Sidebar toggle functionality - FIXED FOR MOBILE VIEW
  const sidebarCollapse = document.getElementById('sidebarCollapse');
  const sidebarCollapseDesktop = document.getElementById('sidebarCollapseDesktop');
  const sidebarClose = document.getElementById('sidebarClose');
  const sidebar = document.getElementById('sidebar');
  const content = document.getElementById('content');
  
  // Mobile sidebar open toggle
  if (sidebarCollapse) {
    sidebarCollapse.addEventListener('click', function(event) {
      event.preventDefault();
      event.stopPropagation();
      sidebar.classList.add('active');
      document.body.classList.add('sidebar-open');
    });
  }
  
  // Mobile sidebar close button
  if (sidebarClose) {
    sidebarClose.addEventListener('click', function(event) {
      event.preventDefault();
      event.stopPropagation();
      sidebar.classList.remove('active');
      document.body.classList.remove('sidebar-open');
    });
  }
  
  // Desktop sidebar toggle
  if (sidebarCollapseDesktop) {
    sidebarCollapseDesktop.addEventListener('click', function() {
      sidebar.classList.toggle('active');
      content.classList.toggle('expanded');
    });
  }
  
  // Close sidebar when clicking outside on mobile
  document.addEventListener('click', function(event) {
    const windowWidth = window.innerWidth;
    if (windowWidth < 768 && 
        sidebar.classList.contains('active') &&
        !sidebar.contains(event.target) && 
        !sidebarCollapse.contains(event.target)) {
      sidebar.classList.remove('active');
      document.body.classList.remove('sidebar-open');
    }
  });
  
  // Close sidebar when ESC key is pressed
  document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape' && sidebar.classList.contains('active') && window.innerWidth < 768) {
      sidebar.classList.remove('active');
      document.body.classList.remove('sidebar-open');
    }
  });

  // Initialize tooltips
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function(tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });
  
  // Initialize popovers
  const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
  popoverTriggerList.map(function(popoverTriggerEl) {
    return new bootstrap.Popover(popoverTriggerEl);
  });
  
  // Auto-hide alerts after 5 seconds
  const alerts = document.querySelectorAll('.alert:not(.alert-persistent)');
  alerts.forEach(function(alert) {
    setTimeout(function() {
      const bsAlert = new bootstrap.Alert(alert);
      bsAlert.close();
    }, 5000);
  });
  
  // Handle form validation styling
  const forms = document.querySelectorAll('.needs-validation');
  Array.from(forms).forEach(function(form) {
    form.addEventListener('submit', function(event) {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      form.classList.add('was-validated');
    }, false);
  });
  
  // Confirm delete modals
  const deleteButtons = document.querySelectorAll('.btn-delete');
  deleteButtons.forEach(function(button) {
    button.addEventListener('click', function(event) {
      event.preventDefault();
      const url = this.getAttribute('href');
      const name = this.getAttribute('data-name');
      
      // Set the item name in the modal
      const itemNameElement = document.getElementById('deleteItemName');
      if (itemNameElement) {
        itemNameElement.textContent = name;
      }
      
      // Set the form action URL
      const deleteForm = document.getElementById('deleteForm');
      if (deleteForm) {
        deleteForm.setAttribute('action', url);
      }
      
      // Show the modal
      const deleteModal = new bootstrap.Modal(document.getElementById('deleteConfirmModal'));
      deleteModal.show();
    });
  });
  
  // File input preview
  const fileInputs = document.querySelectorAll('.custom-file-input');
  fileInputs.forEach(function(input) {
    input.addEventListener('change', function(e) {
      const fileName = e.target.files[0].name;
      const nextSibling = e.target.nextElementSibling;
      nextSibling.innerText = fileName;
      
      // Show image preview if applicable
      const previewElement = document.getElementById(e.target.getAttribute('data-preview'));
      if (previewElement && e.target.files && e.target.files[0]) {
        const reader = new FileReader();
        reader.onload = function(e) {
          previewElement.setAttribute('src', e.target.result);
          previewElement.style.display = 'block';
        }
        reader.readAsDataURL(e.target.files[0]);
      }
    });
  });
  
  // Mark notification as read when clicked
  const notificationItems = document.querySelectorAll('.notification-item');
  notificationItems.forEach(item => {
    item.addEventListener('click', function() {
      const notificationId = this.dataset.notificationId;
      if (notificationId) {
        fetch(`/notifications/${notificationId}/read/`, {
          method: 'POST',
          headers: {
            'X-CSRFToken': getCSRFToken(),
            'Content-Type': 'application/json'
          }
        });
      }
    });
  });
  
  // Get CSRF token
  function getCSRFToken() {
    const cookieValue = document.cookie
      .split('; ')
      .find(row => row.startsWith('csrftoken='))
      ?.split('=')[1];
    
    return cookieValue || '';
  }
});