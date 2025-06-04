// static/js/main.js

/**
 * Main JavaScript file for the Vehicle Management System
 * Enhanced with responsive features for dashboard and multilingual support
 */

document.addEventListener('DOMContentLoaded', function() {
  // Language translations for driver dashboard
  const dashboardTranslations = {
    // English (default)
    en: {
      welcome: "Welcome",
      driver_dashboard: "Driver Dashboard",
      monthly_distance: "Monthly Distance",
      monthly_trips: "Monthly Trips",
      total_hours: "Total Hours",
      fuel_used: "Fuel Used",
      current_trip: "Your Current Trip",
      started: "Started:",
      purpose: "Purpose:",
      start_odometer: "Start Odometer:",
      end_trip: "End Trip",
      details: "Details",
      no_active_trips: "No active trips",
      start_new_trip: "Start New Trip",
      monthly_trip_distance: "Your Monthly Trip Distance",
      driving_hours: "Your Driving Hours",
      daily_activity: "Daily Activity Breakdown",
      daily: "Daily",
      weekly: "Weekly",
      recent_trips: "Your Recent Trips",
      recent_fuel: "Recent Fuel Transactions",
      date: "DATE",
      vehicle: "VEHICLE",
      distance: "DISTANCE",
      duration: "DURATION",
      status: "STATUS",
      actions: "ACTIONS",
      in_progress: "In progress",
      no_recent_trips: "No recent trips",
      no_fuel_transactions: "No recent fuel transactions",
      amount: "AMOUNT",
      km: "km",
      hrs: "hrs",
      liter: "L",
      // Trip status translations
      status_completed: "Completed",
      status_ongoing: "Ongoing",
      status_cancelled: "Cancelled",
      status_scheduled: "Scheduled"
    },
    
    // Tamil translations
    ta: {
      welcome: "வரவேற்கிறோம்",
      driver_dashboard: "ஓட்டுநர் டாஷ்போர்டு",
      monthly_distance: "மாதாந்திர தூரம்",
      monthly_trips: "மாதாந்திர பயணங்கள்",
      total_hours: "மொத்த மணிநேரங்கள்",
      fuel_used: "பயன்படுத்தப்பட்ட எரிபொருள்",
      current_trip: "உங்கள் தற்போதைய பயணம்",
      started: "தொடங்கியது:",
      purpose: "நோக்கம்:",
      start_odometer: "தொடக்க ஓடோமீட்டர்:",
      end_trip: "பயணத்தை முடிக்க",
      details: "விவரங்கள்",
      no_active_trips: "செயலில் உள்ள பயணங்கள் இல்லை",
      start_new_trip: "புதிய பயணத்தைத் தொடங்கு",
      monthly_trip_distance: "உங்கள் மாதாந்திர பயண தூரம்",
      driving_hours: "உங்கள் ஓட்டுநர் மணிநேரங்கள்",
      daily_activity: "தினசரி செயல்பாடு விவரம்",
      daily: "தினசரி",
      weekly: "வாராந்திர",
      recent_trips: "உங்கள் சமீபத்திய பயணங்கள்",
      recent_fuel: "சமீபத்திய எரிபொருள் பரிவர்த்தனைகள்",
      date: "தேதி",
      vehicle: "வாகனம்",
      distance: "தூரம்",
      duration: "காலம்",
      status: "நிலை",
      actions: "செயல்கள்",
      in_progress: "முன்னேற்றத்தில்",
      no_recent_trips: "சமீபத்திய பயணங்கள் இல்லை",
      no_fuel_transactions: "சமீபத்திய எரிபொருள் பரிவர்த்தனைகள் இல்லை",
      amount: "அளவு",
      km: "கி.மீ",
      hrs: "மணி",
      liter: "லி",
      // Trip status translations
      status_completed: "முடிந்தது",
      status_ongoing: "நடந்து கொண்டிருக்கிறது",
      status_cancelled: "ரத்து செய்யப்பட்டது",
      status_scheduled: "திட்டமிடப்பட்டது"
    },
    
    // Malayalam translations
    ml: {
      welcome: "സ്വാഗതം",
      driver_dashboard: "ഡ്രൈവർ ഡാഷ്ബോർഡ്",
      monthly_distance: "പ്രതിമാസ ദൂരം",
      monthly_trips: "പ്രതിമാസ യാത്രകൾ",
      total_hours: "ആകെ മണിക്കൂറുകൾ",
      fuel_used: "ഉപയോഗിച്ച ഇന്ധനം",
      current_trip: "നിങ്ങളുടെ നിലവിലെ യാത്ര",
      started: "ആരംഭിച്ചത്:",
      purpose: "ഉദ്ദേശ്യം:",
      start_odometer: "ആരംഭ ഓഡോമീറ്റർ:",
      end_trip: "യാത്ര അവസാനിപ്പിക്കുക",
      details: "വിശദാംശങ്ങൾ",
      no_active_trips: "സജീവ യാത്രകളൊന്നുമില്ല",
      start_new_trip: "പുതിയ യാത്ര ആരംഭിക്കുക",
      monthly_trip_distance: "നിങ്ങളുടെ പ്രതിമാസ യാത്രാ ദൂരം",
      driving_hours: "നിങ്ങളുടെ ഡ്രൈവിംഗ് മണിക്കൂറുകൾ",
      daily_activity: "ദൈനംദിന പ്രവർത്തന വിശകലനം",
      daily: "ദിവസേന",
      weekly: "ആഴ്ചതോറും",
      recent_trips: "നിങ്ങളുടെ സമീപകാല യാത്രകൾ",
      recent_fuel: "സമീപകാല ഇന്ധന ഇടപാടുകൾ",
      date: "തീയതി",
      vehicle: "വാഹനം",
      distance: "ദൂരം",
      duration: "ദൈർഘ്യം",
      status: "സ്റ്റാറ്റസ്",
      actions: "പ്രവർത്തനങ്ങൾ",
      in_progress: "പുരോഗതിയിൽ",
      no_recent_trips: "സമീപകാല യാത്രകളൊന്നുമില്ല",
      no_fuel_transactions: "സമീപകാല ഇന്ധന ഇടപാടുകളൊന്നുമില്ല",
      amount: "അളവ്",
      km: "കി.മീ",
      hrs: "മണി",
      liter: "ലി",
      // Trip status translations
      status_completed: "പൂർത്തിയായി",
      status_ongoing: "നടന്നുകൊണ്ടിരിക്കുന്നു",
      status_cancelled: "റദ്ദാക്കി",
      status_scheduled: "ഷെഡ്യൂൾ ചെയ്തു"
    }
  };

  // Initialize language functionality for driver dashboard
  function initDriverDashboardLanguage() {
    // Check if we're on the driver dashboard
    if (document.querySelector('[data-lang-key="driver_dashboard"]')) {
      // Current language - default to English
      let currentLang = 'en';
      
      // Language selector buttons
      const languageButtons = document.querySelectorAll('.language-btn');
      
      // Apply translations based on selected language
      function applyTranslations(lang) {
        const langTexts = document.querySelectorAll('.lang-text');
        
        langTexts.forEach(element => {
          const key = element.getAttribute('data-lang-key');
          if (key && dashboardTranslations[lang] && dashboardTranslations[lang][key]) {
            element.textContent = dashboardTranslations[lang][key];
          }
        });
        
        // Update current language
        currentLang = lang;
        
        // Update language buttons active state
        languageButtons.forEach(button => {
          if (button.getAttribute('data-lang') === lang) {
            button.classList.add('active');
          } else {
            button.classList.remove('active');
          }
        });
        
        // Store language preference in localStorage
        localStorage.setItem('driverDashboardLang', lang);
        
        // Update chart labels if charts exist
        updateChartLabels(lang);
      }
      
      // Update chart labels with translated text
      function updateChartLabels(lang) {
        const t = dashboardTranslations[lang];
        
        // Distance Chart
        if (window.distanceChart) {
          window.distanceChart.options.scales.y.title.text = t.distance + ' (' + t.km + ')';
          window.distanceChart.data.datasets[0].label = t.distance + ' (' + t.km + ')';
          window.distanceChart.update();
        }
        
        // Hours Chart
        if (window.hoursChart) {
          window.hoursChart.options.scales.y.title.text = t.driving_hours;
          window.hoursChart.data.datasets[0].label = t.driving_hours;
          window.hoursChart.update();
        }
        
        // Daily Activity Chart
        if (window.dailyActivityChart) {
          window.dailyActivityChart.options.scales.y.title.text = t.hrs;
          window.dailyActivityChart.data.datasets[0].label = t.hrs;
          window.dailyActivityChart.update();
        }
        
        // Weekly Activity Chart
        if (window.weeklyActivityChart) {
          window.weeklyActivityChart.options.scales.y.title.text = t.hrs;
          window.weeklyActivityChart.data.datasets[0].label = t.hrs;
          window.weeklyActivityChart.update();
        }
      }
      
      // Event listeners for language buttons
      languageButtons.forEach(button => {
        button.addEventListener('click', function() {
          const lang = this.getAttribute('data-lang');
          applyTranslations(lang);
        });
      });
      
      // Check for saved language preference
      const savedLang = localStorage.getItem('driverDashboardLang');
      if (savedLang && dashboardTranslations[savedLang]) {
        applyTranslations(savedLang);
      } else {
        // Default to English
        applyTranslations('en');
      }
    }
  }

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

  // ================= RESPONSIVE DASHBOARD ENHANCEMENTS =================

  // Set global chart defaults if Chart.js is loaded
  if (typeof Chart !== 'undefined') {
    Chart.defaults.responsive = true;
    Chart.defaults.maintainAspectRatio = false;
    
    // Get current screen size category
    function getScreenSizeCategory() {
      const width = window.innerWidth;
      if (width < 576) return 'xs';
      if (width < 768) return 'sm';
      if (width < 992) return 'md';
      if (width < 1200) return 'lg';
      return 'xl';
    }
    
    // Generate responsive chart options based on screen size
    function getResponsiveChartOptions() {
      const screenSize = getScreenSizeCategory();
      const isMobile = screenSize === 'xs' || screenSize === 'sm';
      
      return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            position: screenSize === 'xs' ? 'bottom' : 'top',
            labels: {
              boxWidth: isMobile ? 8 : 12,
              font: {
                size: isMobile ? 8 : 11
              }
            }
          },
          tooltip: {
            mode: 'index',
            intersect: false,
            titleFont: {
              size: isMobile ? 10 : 12
            },
            bodyFont: {
              size: isMobile ? 9 : 11
            },
            footerFont: {
              size: isMobile ? 8 : 10
            },
            padding: isMobile ? 6 : 8
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            grid: {
              display: !isMobile
            },
            ticks: {
              font: {
                size: isMobile ? 8 : 10
              },
              maxTicksLimit: isMobile ? 5 : 8
            },
            title: {
              display: !isMobile,
              font: {
                size: isMobile ? 9 : 11
              }
            }
          },
          x: {
            grid: {
              display: !isMobile
            },
            ticks: {
              maxRotation: isMobile ? 90 : 45,
              minRotation: isMobile ? 45 : 0,
              font: {
                size: isMobile ? 8 : 10
              },
              maxTicksLimit: isMobile ? 5 : 10
            }
          }
        },
        layout: {
          padding: {
            left: isMobile ? 0 : 10,
            right: isMobile ? 0 : 10,
            top: isMobile ? 0 : 10,
            bottom: isMobile ? 0 : 10
          }
        },
        animation: {
          duration: isMobile ? 300 : 1000
        }
      };
    }
    
    // Apply responsive options to charts
    function applyResponsiveChartOptions() {
      const options = getResponsiveChartOptions();
      const charts = {
        distanceChart: document.getElementById('distanceChart'),
        hoursChart: document.getElementById('hoursChart'),
        dailyActivityChart: document.getElementById('dailyActivityChart'),
        weeklyActivityChart: document.getElementById('weeklyActivityChart'),
        vehicleStatusChart: document.getElementById('vehicleStatusChart'),
        vehicleTypesChart: document.getElementById('vehicleTypesChart'),
        fuelExpensesMonthlyChart: document.getElementById('fuelExpensesMonthlyChart'),
        fuelExpensesWeeklyChart: document.getElementById('fuelExpensesWeeklyChart'),
        fuelExpensesDailyChart: document.getElementById('fuelExpensesDailyChart'),
        maintenanceStatusChart: document.getElementById('maintenanceStatusChart'),
        vehicleAvailabilityChart: document.getElementById('vehicleAvailabilityChart'),
        fuelEfficiencyChart: document.getElementById('fuelEfficiencyChart')
      };
      
      // Update chart instances if they exist
      for (const chartName in charts) {
        if (charts[chartName] && window[chartName]) {
          // Apply the new options
          const chartInstance = window[chartName];
          chartInstance.options = {...chartInstance.options, ...options};
          chartInstance.update();
        }
      }
    }
    
    // Handle window resize for charts
    let resizeTimeout;
    window.addEventListener('resize', function() {
      // Debounce resize events
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(function() {
        applyResponsiveChartOptions();
        
        // Resize maps if they exist
        if (window.map) {
          window.map.invalidateSize();
        }
      }, 250);
    });
    
    // Initial application of responsive chart options
    setTimeout(applyResponsiveChartOptions, 100);
  }
  
  // Responsive table handling
  function handleResponsiveTables() {
    const tableResponsive = document.querySelectorAll('.table-responsive');
    const screenWidth = window.innerWidth;
    const isMobile = screenWidth < 576;
    
    // Handle column visibility on small screens
    document.querySelectorAll('.hide-xs').forEach(el => {
      el.style.display = isMobile ? 'none' : '';
    });
    
    // Add horizontal scrolling indicators on mobile if table is wider than container
    tableResponsive.forEach(container => {
      const table = container.querySelector('table');
      if (table && container.scrollWidth > container.clientWidth) {
        if (!container.classList.contains('has-scroll-indicator')) {
          container.classList.add('has-scroll-indicator');
          
          // Add scroll indicators if not already present
          if (!container.querySelector('.scroll-indicator')) {
            const leftIndicator = document.createElement('div');
            leftIndicator.className = 'scroll-indicator scroll-indicator-left';
            leftIndicator.innerHTML = '<i class="fas fa-chevron-left"></i>';
            leftIndicator.style.display = 'none';
            
            const rightIndicator = document.createElement('div');
            rightIndicator.className = 'scroll-indicator scroll-indicator-right';
            rightIndicator.innerHTML = '<i class="fas fa-chevron-right"></i>';
            
            container.appendChild(leftIndicator);
            container.appendChild(rightIndicator);
            
            // Add scroll event handler
            container.addEventListener('scroll', function() {
              leftIndicator.style.display = container.scrollLeft > 10 ? 'flex' : 'none';
              rightIndicator.style.display = 
                container.scrollLeft + container.clientWidth >= container.scrollWidth - 10 ? 'none' : 'flex';
            });
          }
        }
      } else {
        container.classList.remove('has-scroll-indicator');
        const indicators = container.querySelectorAll('.scroll-indicator');
        indicators.forEach(indicator => indicator.remove());
      }
    });
  }
  
  // Add swipe support for tables on mobile
  function enableTableSwipe() {
    const tableContainers = document.querySelectorAll('.table-responsive');
    tableContainers.forEach(container => {
      let startX, startY, startScrollLeft, startScrollTop;
      let isDown = false;
      
      container.addEventListener('touchstart', function(e) {
        isDown = true;
        startX = e.touches[0].pageX - container.offsetLeft;
        startY = e.touches[0].pageY - container.offsetTop;
        startScrollLeft = container.scrollLeft;
        startScrollTop = container.scrollTop;
      });
      
      container.addEventListener('touchend', function() {
        isDown = false;
      });
      
      container.addEventListener('touchcancel', function() {
        isDown = false;
      });
      
      container.addEventListener('touchmove', function(e) {
        if (!isDown) return;
        e.preventDefault();
        const x = e.touches[0].pageX - container.offsetLeft;
        const y = e.touches[0].pageY - container.offsetTop;
        const walkX = (x - startX) * 1.5;
        const walkY = (y - startY) * 1.5;
        
        // Determine if scrolling horizontally or vertically based on which direction has more movement
        if (Math.abs(walkX) > Math.abs(walkY)) {
          container.scrollLeft = startScrollLeft - walkX;
        } else {
          container.scrollTop = startScrollTop - walkY;
        }
      });
    });
  }
  
  // Handle button groups on mobile
  function handleResponsiveButtonGroups() {
    const buttonGroups = document.querySelectorAll('.btn-group-responsive');
    const screenWidth = window.innerWidth;
    
    buttonGroups.forEach(group => {
      if (screenWidth < 576) {
        group.classList.add('d-flex', 'flex-column');
        group.querySelectorAll('.btn').forEach(btn => {
          btn.classList.add('w-100', 'mb-2');
          btn.style.borderRadius = '0.25rem';
          btn.style.marginLeft = '0';
        });
      } else {
        group.classList.remove('d-flex', 'flex-column');
        group.querySelectorAll('.btn').forEach(btn => {
          btn.classList.remove('w-100', 'mb-2');
          btn.style.borderRadius = '';
          btn.style.marginLeft = '';
        });
      }
    });
  }
  
  // Apply all responsive enhancements
  function applyResponsiveEnhancements() {
    handleResponsiveTables();
    handleResponsiveButtonGroups();
  }
  
  // Run responsive enhancements on page load
  applyResponsiveEnhancements();
  enableTableSwipe();
  
  // Add responsive event listener
  window.addEventListener('resize', function() {
    applyResponsiveEnhancements();
  });
  
  // Toggle between daily and weekly views
  const dailyViewBtn = document.getElementById('dailyViewBtn');
  const weeklyViewBtn = document.getElementById('weeklyViewBtn');
  const dailyView = document.getElementById('dailyView');
  const weeklyView = document.getElementById('weeklyView');
  
  if (dailyViewBtn && weeklyViewBtn && dailyView && weeklyView) {
    dailyViewBtn.addEventListener('click', function() {
      dailyView.style.display = 'block';
      weeklyView.style.display = 'none';
      dailyViewBtn.classList.add('active');
      weeklyViewBtn.classList.remove('active');
      
      // Resize charts after visibility change
      if (window.dailyActivityChart) {
        setTimeout(() => {
          window.dailyActivityChart.resize();
          window.dailyActivityChart.update();
        }, 50);
      }
    });
    
    weeklyViewBtn.addEventListener('click', function() {
      dailyView.style.display = 'none';
      weeklyView.style.display = 'block';
      dailyViewBtn.classList.remove('active');
      weeklyViewBtn.classList.add('active');
      
      // Resize charts after visibility change
      if (window.weeklyActivityChart) {
        setTimeout(() => {
          window.weeklyActivityChart.resize();
          window.weeklyActivityChart.update();
        }, 50);
      }
    });
  }
  
  // Toggle between fuel expense views
  const monthlyFuelBtn = document.getElementById('monthlyFuelBtn');
  const weeklyFuelBtn = document.getElementById('weeklyFuelBtn');
  const dailyFuelBtn = document.getElementById('dailyFuelBtn');
  const monthlyFuelView = document.getElementById('monthlyFuelView');
  const weeklyFuelView = document.getElementById('weeklyFuelView');
  const dailyFuelView = document.getElementById('dailyFuelView');
  
  if (monthlyFuelBtn && weeklyFuelBtn && dailyFuelBtn) {
    monthlyFuelBtn.addEventListener('click', function() {
      monthlyFuelView.style.display = 'block';
      weeklyFuelView.style.display = 'none';
      dailyFuelView.style.display = 'none';
      monthlyFuelBtn.classList.add('active');
      weeklyFuelBtn.classList.remove('active');
      dailyFuelBtn.classList.remove('active');
      
      // Resize the chart
      if (window.fuelExpensesMonthlyChart) {
        setTimeout(() => {
          window.fuelExpensesMonthlyChart.resize();
          window.fuelExpensesMonthlyChart.update();
        }, 50);
      }
    });
    
    weeklyFuelBtn.addEventListener('click', function() {
      monthlyFuelView.style.display = 'none';
      weeklyFuelView.style.display = 'block';
      dailyFuelView.style.display = 'none';
      monthlyFuelBtn.classList.remove('active');
      weeklyFuelBtn.classList.add('active');
      dailyFuelBtn.classList.remove('active');
      
      // Resize the chart
      if (window.fuelExpensesWeeklyChart) {
        setTimeout(() => {
          window.fuelExpensesWeeklyChart.resize();
          window.fuelExpensesWeeklyChart.update();
        }, 50);
      }
    });
    
    dailyFuelBtn.addEventListener('click', function() {
      monthlyFuelView.style.display = 'none';
      weeklyFuelView.style.display = 'none';
      dailyFuelView.style.display = 'block';
      monthlyFuelBtn.classList.remove('active');
      weeklyFuelBtn.classList.remove('active');
      dailyFuelBtn.classList.add('active');
      
      // Resize the chart
      if (window.fuelExpensesDailyChart) {
        setTimeout(() => {
          window.fuelExpensesDailyChart.resize();
          window.fuelExpensesDailyChart.update();
        }, 50);
      }
    });
  }
  
  // Handle location map modal
  const locationMapModal = document.getElementById('locationMapModal');
  if (locationMapModal) {
    locationMapModal.addEventListener('shown.bs.modal', function() {
      if (window.map) {
        window.map.invalidateSize();
      }
    });
  }
  
  // Add CSS for responsive indicators if not in stylesheet
  const style = document.createElement('style');
  style.textContent = `
    /* Responsive table styles */
    .table-responsive {
      position: relative;
    }
    .has-scroll-indicator {
      padding: 0 15px;
    }
    .scroll-indicator {
      position: absolute;
      top: 0;
      bottom: 0;
      width: 24px;
      background: rgba(0,0,0,0.1);
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1;
      cursor: pointer;
    }
    .scroll-indicator-left {
      left: 0;
    }
    .scroll-indicator-right {
      right: 0;
    }
    
    /* Language selector styles */
    .language-selector {
      margin-bottom: 1rem;
      text-align: right;
    }
    
    .language-btn {
      padding: 0.375rem 0.75rem;
      border-radius: 0.35rem;
      margin-left: 0.25rem;
      background-color: #f8f9fc;
      border: 1px solid #d1d3e2;
      color: #6e707e;
      font-size: 0.875rem;
      cursor: pointer;
      transition: all 0.2s ease;
    }
    
    .language-btn:hover {
      background-color: #eaecf4;
    }
    
    .language-btn.active {
      background-color: #4e73df;
      color: white;
      border-color: #4e73df;
    }
    
    @media (max-width: 576px) {
      .chart-container {
        height: 250px !important;
      }
      .btn-group-responsive {
        flex-direction: column !important;
      }
      .btn-group-responsive .btn {
        width: 100%;
        margin-bottom: 0.25rem;
        border-radius: 0.25rem !important;
      }
      
      /* Mobile optimization for language buttons */
      .language-selector {
        text-align: center;
        margin-bottom: 0.5rem;
      }
      
      .language-btn {
        padding: 0.25rem 0.5rem;
        font-size: 0.75rem;
        margin-bottom: 0.5rem;
      }
      
      /* Ensure proper text direction for different languages */
      [data-lang="ta"] .lang-text,
      [data-lang="ml"] .lang-text {
        font-size: 105%; /* Slightly larger for better readability */
      }
    }
  `;
  document.head.appendChild(style);
  
  // Initialize language functionality for driver dashboard
  initDriverDashboardLanguage();
});