// static/js/geolocation.js

/**
 * Geolocation tracking functionality for the Vehicle Management System
 */

class TripTracker {
  constructor(options) {
    this.tripId = options.tripId;
    this.trackingEnabled = false;
    this.trackingInterval = null;
    this.intervalTime = options.intervalTime || 30000; // Default: 30 seconds
    this.apiUrl = options.apiUrl || '/api/location/update/';
    this.map = null;
    this.mapElement = options.mapElement;
    this.positionMarker = null;
    this.path = [];
    this.pathLine = null;
    this.csrfToken = this.getCSRFToken();
    this.accuracyCircle = null;
    this.statusElement = options.statusElement;
    this.startButton = options.startButton;
    this.stopButton = options.stopButton;
    
    // Bind methods
    this.startTracking = this.startTracking.bind(this);
    this.stopTracking = this.stopTracking.bind(this);
    this.updateLocation = this.updateLocation.bind(this);
    this.handleLocationError = this.handleLocationError.bind(this);
    this.initMap = this.initMap.bind(this);
    this.updateStatus = this.updateStatus.bind(this);
    
    // Initialize
    this.init();
  }
  
  init() {
    // Check if geolocation is supported
    if (!navigator.geolocation) {
      this.updateStatus('Geolocation is not supported by your browser', 'error');
      return;
    }
    
    // Initialize map if element exists
    if (this.mapElement) {
      this.initMap();
    }
    
    // Add event listeners
    if (this.startButton) {
      this.startButton.addEventListener('click', this.startTracking);
    }
    
    if (this.stopButton) {
      this.stopButton.addEventListener('click', this.stopTracking);
    }
  }
  
  initMap() {
    // Create map
    this.map = L.map(this.mapElement).setView([0, 0], 2);
    
    // Add tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(this.map);
    
    // Get initial position
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        this.map.setView([latitude, longitude], 15);
      },
      (error) => {
        console.error('Error getting initial position:', error);
      }
    );
  }
  
  startTracking() {
    if (this.trackingEnabled) {
      this.updateStatus('Tracking already in progress', 'warning');
      return;
    }
    
    // Update UI
    this.updateStatus('Starting location tracking...', 'info');
    
    if (this.startButton) {
      this.startButton.disabled = true;
    }
    
    if (this.stopButton) {
      this.stopButton.disabled = false;
    }
    
    // Enable tracking
    this.trackingEnabled = true;
    
    // Get an immediate first position
    this.updateLocation();
    
    // Set interval for continuous tracking
    this.trackingInterval = setInterval(this.updateLocation, this.intervalTime);
    
    this.updateStatus('Location tracking active', 'success');
  }
  
  stopTracking() {
    if (!this.trackingEnabled) {
      this.updateStatus('Tracking is not active', 'warning');
      return;
    }
    
    // Clear the tracking interval
    clearInterval(this.trackingInterval);
    this.trackingInterval = null;
    this.trackingEnabled = false;
    
    // Update UI
    this.updateStatus('Location tracking stopped', 'info');
    
    if (this.startButton) {
      this.startButton.disabled = false;
    }
    
    if (this.stopButton) {
      this.stopButton.disabled = true;
    }
  }
  
  updateLocation() {
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude, altitude, accuracy, speed } = position.coords;
        
        // Update map if it exists
        if (this.map) {
          this.updateMapPosition(position.coords);
        }
        
        // Send position to server
        this.sendPositionToServer({
          latitude,
          longitude,
          altitude: altitude || null,
          speed: speed || null,
          trip: this.tripId
        });
      },
      this.handleLocationError,
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 5000
      }
    );
  }
  
  updateMapPosition(coords) {
    const { latitude, longitude, accuracy } = coords;
    const position = [latitude, longitude];
    
    // Update marker or create new one
    if (this.positionMarker) {
      this.positionMarker.setLatLng(position);
    } else {
      this.positionMarker = L.marker(position).addTo(this.map);
    }
    
    // Update accuracy circle
    if (accuracy) {
      if (this.accuracyCircle) {
        this.accuracyCircle.setLatLng(position).setRadius(accuracy);
      } else {
        this.accuracyCircle = L.circle(position, {
          radius: accuracy,
          color: 'blue',
          fillColor: '#3388ff',
          fillOpacity: 0.1
        }).addTo(this.map);
      }
    }
    
    // Update path
    this.path.push(position);
    
    // Update or create path line
    if (this.pathLine) {
      this.pathLine.setLatLngs(this.path);
    } else if (this.path.length > 1) {
      this.pathLine = L.polyline(this.path, {color: 'blue'}).addTo(this.map);
    }
    
    // Center map on current position
    this.map.panTo(position);
  }
  
  sendPositionToServer(data) {
    fetch(this.apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': this.csrfToken
      },
      body: JSON.stringify(data)
    })
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        this.updateStatus('Location updated successfully', 'success');
      })
      .catch(error => {
        console.error('Error sending location data:', error);
        this.updateStatus(`Error updating location: ${error.message}`, 'error');
      });
  }
  
  handleLocationError(error) {
    let message;
    switch(error.code) {
      case error.PERMISSION_DENIED:
        message = "Location access denied. Please enable location services.";
        break;
      case error.POSITION_UNAVAILABLE:
        message = "Location information is unavailable.";
        break;
      case error.TIMEOUT:
        message = "Location request timed out.";
        break;
      case error.UNKNOWN_ERROR:
        message = "An unknown error occurred while getting location.";
        break;
    }
    
    this.updateStatus(message, 'error');
    console.error('Geolocation error:', error);
  }
  
  updateStatus(message, type = 'info') {
    if (!this.statusElement) return;
    
    this.statusElement.textContent = message;
    
    // Remove all status classes
    this.statusElement.classList.remove('text-success', 'text-danger', 'text-warning', 'text-info');
    
    // Add appropriate class
    switch(type) {
      case 'success':
        this.statusElement.classList.add('text-success');
        break;
      case 'error':
        this.statusElement.classList.add('text-danger');
        break;
      case 'warning':
        this.statusElement.classList.add('text-warning');
        break;
      case 'info':
        this.statusElement.classList.add('text-info');
        break;
    }
  }
  
  getCSRFToken() {
    const cookieValue = document.cookie
      .split('; ')
      .find(row => row.startsWith('csrftoken='))
      ?.split('=')[1];
    
    return cookieValue || '';
  }
}

// Trip map view functionality (for viewing trip details)
class TripMapViewer {
  constructor(options) {
    this.tripId = options.tripId;
    this.mapElement = options.mapElement;
    this.apiUrl = options.apiUrl || `/api/location-logs/?trip=${this.tripId}`;
    this.map = null;
    this.markers = [];
    this.path = [];
    this.pathLine = null;
    this.vehicleMarker = null;
    
    // Initialize
    this.init();
  }
  
  init() {
    if (!this.mapElement) return;
    
    // Create map
    this.map = L.map(this.mapElement).setView([0, 0], 2);
    
    // Add tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(this.map);
    
    // Load trip data
    this.loadTripData();
  }
  
  loadTripData() {
    fetch(this.apiUrl)
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        this.processLocationData(data);
      })
      .catch(error => {
        console.error('Error loading trip data:', error);
        // Show error on map
        this.showMapError('Error loading trip data');
      });
  }
  
  processLocationData(locations) {
    if (!locations || locations.length === 0) {
      this.showMapError('No location data available for this trip');
      return;
    }
    
    // Create path and markers
    this.path = locations.map(location => [location.latitude, location.longitude]);
    
    // Create path line
    this.pathLine = L.polyline(this.path, {color: 'blue'}).addTo(this.map);
    
    // Add start and end markers
    const startLocation = locations[0];
    const endLocation = locations[locations.length - 1];
    
    // Start marker (green)
    const startMarker = L.marker([startLocation.latitude, startLocation.longitude], {
      icon: L.divIcon({
        className: 'custom-div-icon',
        html: `<div class="marker-pin marker-pin-start"></div><i class="fas fa-play-circle marker-icon"></i>`,
        iconSize: [30, 42],
        iconAnchor: [15, 42]
      })
    }).addTo(this.map);
    
    startMarker.bindPopup(`
      <strong>Trip Start</strong><br>
      Time: ${new Date(startLocation.timestamp).toLocaleString()}<br>
      ${startLocation.speed ? `Speed: ${(startLocation.speed * 3.6).toFixed(1)} km/h` : ''}
    `);
    
    // End marker (red)
    const endMarker = L.marker([endLocation.latitude, endLocation.longitude], {
      icon: L.divIcon({
        className: 'custom-div-icon',
        html: `<div class="marker-pin marker-pin-end"></div><i class="fas fa-flag-checkered marker-icon"></i>`,
        iconSize: [30, 42],
        iconAnchor: [15, 42]
      })
    }).addTo(this.map);
    
    endMarker.bindPopup(`
      <strong>Latest Position</strong><br>
      Time: ${new Date(endLocation.timestamp).toLocaleString()}<br>
      ${endLocation.speed ? `Speed: ${(endLocation.speed * 3.6).toFixed(1)} km/h` : ''}
    `);
    
    // Add vehicle marker at the latest position (for ongoing trips)
    this.vehicleMarker = L.marker([endLocation.latitude, endLocation.longitude], {
      icon: L.divIcon({
        className: 'custom-div-icon',
        html: `<div class="marker-pin marker-pin-vehicle"></div><i class="fas fa-car marker-icon"></i>`,
        iconSize: [30, 42],
        iconAnchor: [15, 42]
      })
    }).addTo(this.map);
    
    // Add markers for additional points (optional)
    if (locations.length > 10) {
      // Only add markers for some points to avoid cluttering
      const step = Math.ceil(locations.length / 10);
      for (let i = step; i < locations.length - step; i += step) {
        const location = locations[i];
        const marker = L.circleMarker([location.latitude, location.longitude], {
          color: 'blue',
          radius: 5
        }).addTo(this.map);
        
        marker.bindPopup(`
          <strong>Location Point</strong><br>
          Time: ${new Date(location.timestamp).toLocaleString()}<br>
          ${location.speed ? `Speed: ${(location.speed * 3.6).toFixed(1)} km/h` : ''}
        `);
        
        this.markers.push(marker);
      }
    }
    
    // Fit map to path bounds
    this.map.fitBounds(this.pathLine.getBounds(), {
      padding: [50, 50]
    });
  }
  
  showMapError(message) {
    // Center the map
    this.map.setView([0, 0], 2);
    
    // Show error popup
    L.popup()
      .setLatLng([0, 0])
      .setContent(`<div class="text-danger">${message}</div>`)
      .openOn(this.map);
  }
}