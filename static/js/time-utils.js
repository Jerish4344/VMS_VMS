/**
 * Time Utilities for Generator Management System
 * Handles real-time time updates and calculations
 */

class TimeManager {
    constructor() {
        this.intervals = new Map();
        this.initializeTimeElements();
    }

    /**
     * Initialize all time-related elements on the page
     */
    initializeTimeElements() {
        // Update time displays every second
        this.startRealtimeUpdates();
        
        // Initialize time input validation
        this.initializeTimeInputs();
        
        // Initialize duration calculations
        this.initializeDurationCalculations();
    }

    /**
     * Start real-time updates for time displays
     */
    startRealtimeUpdates() {
        // Update all elements with real-time time
        const updateCurrentTime = () => {
            const now = new Date();
            
            // Update current time displays
            document.querySelectorAll('.current-time').forEach(element => {
                element.textContent = now.toLocaleTimeString();
            });
            
            // Update current date displays
            document.querySelectorAll('.current-date').forEach(element => {
                element.textContent = now.toLocaleDateString();
            });
            
            // Update relative time displays (e.g., "2 minutes ago")
            document.querySelectorAll('[data-timestamp]').forEach(element => {
                const timestamp = new Date(element.dataset.timestamp);
                element.textContent = this.getRelativeTime(timestamp, now);
            });
        };

        // Update immediately and then every second
        updateCurrentTime();
        setInterval(updateCurrentTime, 1000);
    }

    /**
     * Initialize time input validation and auto-calculation
     */
    initializeTimeInputs() {
        const startTimeInputs = document.querySelectorAll('input[name="start_time"], input[id*="start_time"]');
        const endTimeInputs = document.querySelectorAll('input[name="end_time"], input[id*="end_time"]');

        // Add event listeners for automatic duration calculation
        [...startTimeInputs, ...endTimeInputs].forEach(input => {
            input.addEventListener('change', this.calculateDuration.bind(this));
            input.addEventListener('input', this.calculateDuration.bind(this));
        });
    }

    /**
     * Initialize duration calculation displays
     */
    initializeDurationCalculations() {
        // Find all duration calculation containers
        document.querySelectorAll('.duration-calculator').forEach(container => {
            this.setupDurationCalculator(container);
        });
    }

    /**
     * Setup a duration calculator for a specific container
     */
    setupDurationCalculator(container) {
        const startInput = container.querySelector('input[name*="start_time"], input[id*="start_time"]');
        const endInput = container.querySelector('input[name*="end_time"], input[id*="end_time"]');
        const durationDisplay = container.querySelector('.duration-display');

        if (startInput && endInput && durationDisplay) {
            const updateDuration = () => {
                const duration = this.calculateTimeDifference(startInput.value, endInput.value);
                durationDisplay.textContent = duration;
                
                // Add visual feedback
                if (duration === 'Invalid time range') {
                    durationDisplay.className = 'duration-display text-danger';
                } else {
                    durationDisplay.className = 'duration-display text-success';
                }
            };

            startInput.addEventListener('change', updateDuration);
            endInput.addEventListener('change', updateDuration);
            
            // Initial calculation
            updateDuration();
        }
    }

    /**
     * Calculate duration and update displays
     */
    calculateDuration(event) {
        const form = event.target.closest('form');
        if (!form) return;

        const startTimeInput = form.querySelector('input[name="start_time"], input[id*="start_time"]');
        const endTimeInput = form.querySelector('input[name="end_time"], input[id*="end_time"]');
        const durationDisplays = form.querySelectorAll('.calculated-duration, .duration-display, .hours-display');

        if (startTimeInput && endTimeInput && startTimeInput.value && endTimeInput.value) {
            const duration = this.calculateTimeDifference(startTimeInput.value, endTimeInput.value);
            
            durationDisplays.forEach(display => {
                display.textContent = duration;
                
                // Add appropriate CSS classes
                if (duration === 'Invalid time range') {
                    display.className = display.className.replace(/text-(success|warning|info)/g, '') + ' text-danger';
                } else {
                    display.className = display.className.replace(/text-(danger|warning|info)/g, '') + ' text-success';
                }
            });
        }
    }

    /**
     * Calculate time difference between two time strings
     */
    calculateTimeDifference(startTime, endTime) {
        if (!startTime || !endTime) return '--:--';

        try {
            const today = new Date().toISOString().split('T')[0]; // Get today's date
            const start = new Date(`${today}T${startTime}`);
            let end = new Date(`${today}T${endTime}`);

            // Handle overnight running (if end time is before start time)
            if (end < start) {
                end.setDate(end.getDate() + 1);
            }

            const diffMs = end - start;
            if (diffMs <= 0) return 'Invalid time range';

            const hours = Math.floor(diffMs / (1000 * 60 * 60));
            const minutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

            if (hours === 0) {
                return `${minutes} minutes`;
            } else if (minutes === 0) {
                return `${hours} hour${hours !== 1 ? 's' : ''}`;
            } else {
                return `${hours} hour${hours !== 1 ? 's' : ''} ${minutes} minute${minutes !== 1 ? 's' : ''}`;
            }
        } catch (error) {
            console.error('Error calculating time difference:', error);
            return 'Error calculating time';
        }
    }

    /**
     * Get relative time string (e.g., "2 minutes ago", "in 1 hour")
     */
    getRelativeTime(timestamp, now = new Date()) {
        const diffMs = now - timestamp;
        const diffSeconds = Math.floor(diffMs / 1000);
        const diffMinutes = Math.floor(diffSeconds / 60);
        const diffHours = Math.floor(diffMinutes / 60);
        const diffDays = Math.floor(diffHours / 24);

        if (diffSeconds < 60) {
            return diffSeconds <= 5 ? 'Just now' : `${diffSeconds} seconds ago`;
        } else if (diffMinutes < 60) {
            return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`;
        } else if (diffHours < 24) {
            return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
        } else {
            return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
        }
    }

    /**
     * Format time for display
     */
    formatTime(date) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    /**
     * Format date for display
     */
    formatDate(date) {
        return date.toLocaleDateString([], { 
            year: 'numeric', 
            month: 'short', 
            day: 'numeric' 
        });
    }

    /**
     * Add live time validation to forms
     */
    addTimeValidation(formElement) {
        const startInput = formElement.querySelector('input[name*="start_time"]');
        const endInput = formElement.querySelector('input[name*="end_time"]');

        if (startInput && endInput) {
            const validateTimes = () => {
                const startTime = startInput.value;
                const endTime = endInput.value;

                if (startTime && endTime) {
                    const duration = this.calculateTimeDifference(startTime, endTime);
                    const isValid = duration !== 'Invalid time range';

                    // Update form validation state
                    startInput.setCustomValidity(isValid ? '' : 'Invalid time range');
                    endInput.setCustomValidity(isValid ? '' : 'End time must be after start time');

                    // Add visual feedback
                    [startInput, endInput].forEach(input => {
                        input.classList.toggle('is-valid', isValid);
                        input.classList.toggle('is-invalid', !isValid);
                    });
                }
            };

            startInput.addEventListener('change', validateTimes);
            endInput.addEventListener('change', validateTimes);
        }
    }

    /**
     * Initialize time picker with current time default
     */
    initializeTimePickerDefaults() {
        document.querySelectorAll('input[type="time"]').forEach(input => {
            if (!input.value && input.dataset.defaultCurrent === 'true') {
                const now = new Date();
                input.value = now.toTimeString().slice(0, 5); // HH:MM format
            }
        });
    }

    /**
     * Clean up intervals when page is unloaded
     */
    cleanup() {
        this.intervals.forEach(interval => clearInterval(interval));
        this.intervals.clear();
    }
}

// Initialize TimeManager when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.timeManager = new TimeManager();
    
    // Initialize time picker defaults
    window.timeManager.initializeTimePickerDefaults();
    
    // Add validation to existing forms
    document.querySelectorAll('form').forEach(form => {
        window.timeManager.addTimeValidation(form);
    });
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (window.timeManager) {
        window.timeManager.cleanup();
    }
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TimeManager;
}
