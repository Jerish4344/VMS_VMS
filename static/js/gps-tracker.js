/**
 * GPS Tracking Module for VMS
 * Tracks staff location during personal vehicle trips to prevent mileage fraud
 * Uses HTML5 Geolocation API - no external dependencies required
 */

class GPSTracker {
  constructor() {
    this.isTracking = false;
    this.trackingInterval = null;
    this.tripId = null;
    this.locationCount = 0;
    this.lastLocation = null;
    this.trackingIntervalSeconds = 20; // Send GPS data every 20 seconds
    this.permissionGranted = false;
  }

  /**
   * Check if browser supports GPS tracking
   */
  isSupported() {
    return 'geolocation' in navigator;
  }

  /**
   * Request GPS permission from user
   * Returns promise that resolves with permission status
   */
  async requestPermission() {
    if (!this.isSupported()) {
      throw new Error('GPS tracking is not supported by your browser. Please use a modern browser like Chrome, Firefox, or Safari.');
    }

    return new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          this.permissionGranted = true;
          this.lastLocation = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy
          };
          resolve({
            granted: true,
            location: this.lastLocation
          });
        },
        (error) => {
          this.permissionGranted = false;
          let message = 'GPS permission denied.';
          
          switch(error.code) {
            case error.PERMISSION_DENIED:
              message = 'GPS permission denied. Please enable location access in your browser settings to start the trip.';
              break;
            case error.POSITION_UNAVAILABLE:
              message = 'GPS signal unavailable. Please ensure location services are enabled on your device.';
              break;
            case error.TIMEOUT:
              message = 'GPS request timed out. Please check your location settings and try again.';
              break;
          }
          
          reject(new Error(message));
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 0
        }
      );
    });
  }

  /**
   * Start tracking GPS location for a trip
   * @param {number} tripId - The trip ID to track
   */
  async startTracking(tripId) {
    if (!this.permissionGranted) {
      throw new Error('GPS permission not granted. Please request permission first.');
    }

    if (this.isTracking) {
      console.warn('GPS tracking already active for trip', this.tripId);
      return;
    }

    this.tripId = tripId;
    this.isTracking = true;
    this.locationCount = 0;

    // Send initial location immediately
    await this.sendCurrentLocation();

    // Start periodic tracking
    this.trackingInterval = setInterval(() => {
      this.sendCurrentLocation().catch(error => {
        console.error('Failed to send GPS location:', error);
      });
    }, this.trackingIntervalSeconds * 1000);

    console.log(`GPS tracking started for trip ${tripId}`);
    this.updateUI('tracking');
  }

  /**
   * Stop tracking GPS location
   */
  stopTracking() {
    if (!this.isTracking) {
      return;
    }

    if (this.trackingInterval) {
      clearInterval(this.trackingInterval);
      this.trackingInterval = null;
    }

    this.isTracking = false;
    console.log(`GPS tracking stopped for trip ${this.tripId}`);
    this.updateUI('stopped');
  }

  /**
   * Get current GPS location and send to server
   */
  async sendCurrentLocation() {
    return new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          const locationData = {
            trip_id: this.tripId,
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
            speed: position.coords.speed || null,
            altitude: position.coords.altitude || null,
            heading: position.coords.heading || null,
            battery_level: await this.getBatteryLevel()
          };

          try {
            const response = await fetch('/trips/api/gps/record/', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
              },
              body: JSON.stringify(locationData)
            });

            if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            
            if (result.success) {
              this.locationCount = result.total_points;
              this.lastLocation = {
                latitude: position.coords.latitude,
                longitude: position.coords.longitude,
                accuracy: position.coords.accuracy,
                timestamp: new Date()
              };
              this.updateUI('location_sent');
              resolve(result);
            } else {
              throw new Error(result.error || 'Failed to record location');
            }
          } catch (error) {
            console.error('Error sending GPS data:', error);
            reject(error);
          }
        },
        (error) => {
          console.error('GPS position error:', error);
          reject(error);
        },
        {
          enableHighAccuracy: true,
          timeout: 5000,
          maximumAge: 1000
        }
      );
    });
  }

  /**
   * Get current battery level if Battery Status API is available
   */
  async getBatteryLevel() {
    try {
      if ('getBattery' in navigator) {
        const battery = await navigator.getBattery();
        return Math.round(battery.level * 100);
      }
    } catch (error) {
      console.warn('Battery API not available:', error);
    }
    return null;
  }

  /**
   * Get CSRF token from cookie for Django
   */
  getCSRFToken() {
    const name = 'csrftoken';
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  /**
   * Finalize GPS tracking and calculate distance
   * @param {number} endOdometer - Optional end odometer reading
   */
  async finalize(endOdometer = null) {
    if (!this.tripId) {
      throw new Error('No active trip to finalize');
    }

    this.stopTracking();

    try {
      const body = endOdometer ? JSON.stringify({ end_odometer: endOdometer }) : JSON.stringify({});
      
      const response = await fetch(`/trips/api/gps/finalize/${this.tripId}/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.getCSRFToken()
        },
        body: body
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      
      if (result.success) {
        return {
          gps_distance: result.gps_distance,
          odometer_distance: result.odometer_distance,
          variance_percentage: result.variance_percentage,
          requires_review: result.requires_review,
          review_reason: result.review_reason
        };
      } else {
        throw new Error(result.error || 'Failed to finalize GPS tracking');
      }
    } catch (error) {
      console.error('Error finalizing GPS tracking:', error);
      throw error;
    }
  }

  /**
   * Get tracking status for a trip
   */
  async getStatus(tripId) {
    try {
      const response = await fetch(`/trips/api/gps/status/${tripId}/`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error getting GPS status:', error);
      throw error;
    }
  }

  /**
   * Update UI elements to show GPS tracking status
   */
  updateUI(status) {
    const indicator = document.getElementById('gps-tracking-indicator');
    const counter = document.getElementById('gps-location-count');

    if (!indicator) return;

    switch(status) {
      case 'tracking':
        indicator.innerHTML = '<i class="fas fa-map-marker-alt"></i> GPS Tracking Active';
        indicator.className = 'alert alert-success mb-3';
        indicator.style.display = 'block';
        break;
      
      case 'stopped':
        indicator.innerHTML = '<i class="fas fa-stop-circle"></i> GPS Tracking Stopped';
        indicator.className = 'alert alert-warning mb-3';
        break;
      
      case 'location_sent':
        if (counter) {
          counter.textContent = this.locationCount;
        }
        
        if (this.lastLocation) {
          const accuracy = Math.round(this.lastLocation.accuracy);
          const accuracyClass = accuracy < 20 ? 'success' : accuracy < 50 ? 'warning' : 'danger';
          
          indicator.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
              <span><i class="fas fa-map-marker-alt"></i> GPS Tracking Active</span>
              <small class="text-muted">
                Points: <strong>${this.locationCount}</strong> | 
                Accuracy: <span class="badge bg-${accuracyClass}">${accuracy}m</span> |
                Last: ${new Date(this.lastLocation.timestamp).toLocaleTimeString()}
              </small>
            </div>
          `;
        }
        break;
    }
  }

  /**
   * Reset tracker state
   */
  reset() {
    this.stopTracking();
    this.tripId = null;
    this.locationCount = 0;
    this.lastLocation = null;
    this.permissionGranted = false;
  }
}

// Create global instance
window.gpsTracker = new GPSTracker();
