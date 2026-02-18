// static/js/geolocation.js

/**
 * Geolocation tracking functionality for the Vehicle Management System
 * Using Leaflet (OpenStreetMap) - No API key required
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
  
  async init() {
    // Check if geolocation is supported
    if (!navigator.geolocation) {
      this.updateStatus('Geolocation is not supported by your browser', 'error');
      return;
    }
    
    try {
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
    } catch (error) {
      console.error('Error initializing map:', error);
      this.updateStatus('Failed to load map', 'error');
    }
  }
  
  initMap() {
    // Create map with default center using Leaflet
    this.map = L.map(this.mapElement).setView([0, 0], 2);
    
    // Add OpenStreetMap tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19
    }).addTo(this.map);
    
    // Initialize path polyline
    this.pathLine = L.polyline([], {
      color: '#FF0000',
      weight: 3,
      opacity: 1
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
          accuracy: accuracy || 0,
          altitude: altitude || null,
          speed: speed || null,
          trip_id: this.tripId
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
    
    // Create custom icon for current position
    const currentPositionIcon = L.divIcon({
      className: 'current-position-marker',
      html: '<div style="width: 24px; height: 24px; background-color: #4285F4; border: 3px solid white; border-radius: 50%; box-shadow: 0 2px 6px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center;"><div style="width: 8px; height: 8px; background-color: white; border-radius: 50%;"></div></div>',
      iconSize: [24, 24],
      iconAnchor: [12, 12]
    });
    
    // Update marker or create new one
    if (this.positionMarker) {
      this.positionMarker.setLatLng(position);
    } else {
      this.positionMarker = L.marker(position, { icon: currentPositionIcon }).addTo(this.map);
      this.positionMarker.bindPopup('Current Position');
    }
    
    // Update accuracy circle
    if (accuracy) {
      if (this.accuracyCircle) {
        this.accuracyCircle.setLatLng(position);
        this.accuracyCircle.setRadius(accuracy);
      } else {
        this.accuracyCircle = L.circle(position, {
          color: '#4285F4',
          fillColor: '#4285F4',
          fillOpacity: 0.1,
          radius: accuracy
        }).addTo(this.map);
      }
    }
    
    // Update path
    this.path.push(position);
    this.pathLine.setLatLngs(this.path);
    
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
          throw new Error('HTTP error! Status: ' + response.status);
        }
        return response.json();
      })
      .then(data => {
        this.updateStatus('Location updated successfully', 'success');
      })
      .catch(error => {
        console.error('Error sending location data:', error);
        this.updateStatus('Error updating location: ' + error.message, 'error');
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
  
  updateStatus(message, type) {
    type = type || 'info';
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
      .find(function(row) { return row.startsWith('csrftoken='); });
    
    return cookieValue ? cookieValue.split('=')[1] : '';
  }
}

// Trip map view functionality (for viewing trip details)
class TripMapViewer {
  constructor(options) {
    this.tripId = options.tripId;
    this.mapElement = options.mapElement;
    this.apiUrl = options.apiUrl || '/trips/api/gps/locations/' + this.tripId + '/';
    this.map = null;
    this.markers = [];
    this.path = [];
    this.pathLine = null;
    this.vehicleMarker = null;
    
    // Initialize
    this.init();
  }
  
  async init() {
    if (!this.mapElement) return;
    
    try {
      // Create map using Leaflet
      this.map = L.map(this.mapElement).setView([0, 0], 2);
      
      // Add OpenStreetMap tile layer
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19
      }).addTo(this.map);
      
      // Initialize path polyline
      this.pathLine = L.polyline([], {
        color: '#FF0000',
        weight: 3,
        opacity: 1
      }).addTo(this.map);
      
      // Load trip data
      this.loadTripData();
    } catch (error) {
      console.error('Error initializing map:', error);
      this.showMapError('Failed to load map');
    }
  }
  
  loadTripData() {
    var self = this;
    fetch(this.apiUrl)
      .then(function(response) {
        if (!response.ok) {
          throw new Error('HTTP error! Status: ' + response.status);
        }
        return response.json();
      })
      .then(function(data) {
        self.processLocationData(data);
      })
      .catch(function(error) {
        console.error('Error loading trip data:', error);
        self.showMapError('Error loading trip data');
      });
  }
  
  processLocationData(locations) {
    var self = this;
    if (!locations || locations.length === 0) {
      this.showMapError('No location data available for this trip');
      return;
    }
    
    // Create path
    this.path = locations.map(function(location) {
      return [location.latitude, location.longitude];
    });
    
    // Update path line
    this.pathLine.setLatLngs(this.path);
    
    // Create green icon for start
    var greenIcon = L.divIcon({
      className: 'custom-marker',
      html: '<div style="background-color: #28a745; width: 15px; height: 15px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.3);"></div>',
      iconSize: [15, 15],
      iconAnchor: [7, 7]
    });
    
    // Create red icon for end/latest
    var redIcon = L.divIcon({
      className: 'custom-marker',
      html: '<div style="background-color: #dc3545; width: 15px; height: 15px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.3);"></div>',
      iconSize: [15, 15],
      iconAnchor: [7, 7]
    });
    
    // Add start marker (green)
    var startLocation = locations[0];
    var startMarker = L.marker([startLocation.latitude, startLocation.longitude], { icon: greenIcon }).addTo(this.map);
    startMarker.bindPopup(
      '<div><strong>Trip Start</strong><br>Time: ' + new Date(startLocation.timestamp).toLocaleString() + '<br>' +
      (startLocation.speed ? 'Speed: ' + (startLocation.speed * 3.6).toFixed(1) + ' km/h' : '') + '</div>'
    );
    
    // Add end marker (red)
    var endLocation = locations[locations.length - 1];
    var endMarker = L.marker([endLocation.latitude, endLocation.longitude], { icon: redIcon }).addTo(this.map);
    endMarker.bindPopup(
      '<div><strong>Latest Position</strong><br>Time: ' + new Date(endLocation.timestamp).toLocaleString() + '<br>' +
      (endLocation.speed ? 'Speed: ' + (endLocation.speed * 3.6).toFixed(1) + ' km/h' : '') + '</div>'
    ).openPopup();
    
    // Add intermediate markers if there are many points
    if (locations.length > 10) {
      var blueIcon = L.divIcon({
        className: 'custom-marker',
        html: '<div style="background-color: #007bff; width: 10px; height: 10px; border-radius: 50%; border: 1px solid white;"></div>',
        iconSize: [10, 10],
        iconAnchor: [5, 5]
      });
      
      var step = Math.ceil(locations.length / 10);
      for (var i = step; i < locations.length - step; i += step) {
        var location = locations[i];
        var marker = L.marker([location.latitude, location.longitude], { icon: blueIcon }).addTo(this.map);
        marker.bindPopup(
          '<div><strong>Location Point</strong><br>Time: ' + new Date(location.timestamp).toLocaleString() + '<br>' +
          (location.speed ? 'Speed: ' + (location.speed * 3.6).toFixed(1) + ' km/h' : '') + '</div>'
        );
        this.markers.push(marker);
      }
    }
    
    // Fit map to show all markers
    this.map.fitBounds(this.pathLine.getBounds(), { padding: [50, 50] });
  }
  
  showMapError(message) {
    // Center the map
    this.map.setView([0, 0], 2);
    
    // Show error popup
    L.popup()
      .setLatLng([0, 0])
      .setContent('<div style="color: red;">' + message + '</div>')
      .openOn(this.map);
  }
}
