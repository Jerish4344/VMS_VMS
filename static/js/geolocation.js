// static/js/geolocation.js

/**
 * Geolocation tracking functionality for the Vehicle Management System
 * Using Google Maps API
 */

// Google Maps API configuration
const GOOGLE_MAPS_CONFIG = {
  apiKey: 'AIzaSyDMAkESwj75ZhnMIlLK25zHiM1oAUPZtbo', // Replace with your actual API key
  libraries: ['geometry', 'places']
};

// Load Google Maps API
function loadGoogleMapsAPI() {
  return new Promise((resolve, reject) => {
    if (window.google && window.google.maps) {
      resolve(window.google.maps);
      return;
    }

    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_CONFIG.apiKey}&libraries=${GOOGLE_MAPS_CONFIG.libraries.join(',')}`;
    script.async = true;
    script.defer = true;
    
    script.onload = () => {
      if (window.google && window.google.maps) {
        resolve(window.google.maps);
      } else {
        reject(new Error('Google Maps API failed to load'));
      }
    };
    
    script.onerror = () => {
      reject(new Error('Failed to load Google Maps API script'));
    };
    
    document.head.appendChild(script);
  });
}

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
      // Load Google Maps API
      await loadGoogleMapsAPI();
      
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
      console.error('Error initializing Google Maps:', error);
      this.updateStatus('Failed to load Google Maps', 'error');
    }
  }
  
  initMap() {
    // Create map with default center
    this.map = new google.maps.Map(this.mapElement, {
      zoom: 2,
      center: { lat: 0, lng: 0 },
      mapTypeId: google.maps.MapTypeId.ROADMAP,
      zoomControl: true,
      mapTypeControl: true,
      scaleControl: true,
      streetViewControl: true,
      rotateControl: true,
      fullscreenControl: true
    });
    
    // Initialize path polyline
    this.pathLine = new google.maps.Polyline({
      path: [],
      geodesic: true,
      strokeColor: '#FF0000',
      strokeOpacity: 1.0,
      strokeWeight: 3
    });
    this.pathLine.setMap(this.map);
    
    // Get initial position
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        const initialPos = { lat: latitude, lng: longitude };
        this.map.setCenter(initialPos);
        this.map.setZoom(15);
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
    const position = { lat: latitude, lng: longitude };
    
    // Update marker or create new one
    if (this.positionMarker) {
      this.positionMarker.setPosition(position);
    } else {
      this.positionMarker = new google.maps.Marker({
        position: position,
        map: this.map,
        title: 'Current Position',
        icon: {
          url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(`
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="12" cy="12" r="8" fill="#4285F4" stroke="#ffffff" stroke-width="2"/>
              <circle cx="12" cy="12" r="3" fill="#ffffff"/>
            </svg>
          `),
          scaledSize: new google.maps.Size(24, 24),
          anchor: new google.maps.Point(12, 12)
        }
      });
    }
    
    // Update accuracy circle
    if (accuracy) {
      if (this.accuracyCircle) {
        this.accuracyCircle.setCenter(position);
        this.accuracyCircle.setRadius(accuracy);
      } else {
        this.accuracyCircle = new google.maps.Circle({
          strokeColor: '#4285F4',
          strokeOpacity: 0.8,
          strokeWeight: 1,
          fillColor: '#4285F4',
          fillOpacity: 0.1,
          map: this.map,
          center: position,
          radius: accuracy
        });
      }
    }
    
    // Update path
    this.path.push(position);
    this.pathLine.setPath(this.path);
    
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
  
  async init() {
    if (!this.mapElement) return;
    
    try {
      // Load Google Maps API
      await loadGoogleMapsAPI();
      
      // Create map
      this.map = new google.maps.Map(this.mapElement, {
        zoom: 2,
        center: { lat: 0, lng: 0 },
        mapTypeId: google.maps.MapTypeId.ROADMAP
      });
      
      // Initialize path polyline
      this.pathLine = new google.maps.Polyline({
        path: [],
        geodesic: true,
        strokeColor: '#FF0000',
        strokeOpacity: 1.0,
        strokeWeight: 3
      });
      this.pathLine.setMap(this.map);
      
      // Load trip data
      this.loadTripData();
    } catch (error) {
      console.error('Error initializing Google Maps:', error);
      this.showMapError('Failed to load Google Maps');
    }
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
        this.showMapError('Error loading trip data');
      });
  }
  
  processLocationData(locations) {
    if (!locations || locations.length === 0) {
      this.showMapError('No location data available for this trip');
      return;
    }
    
    // Create path
    this.path = locations.map(location => ({
      lat: location.latitude,
      lng: location.longitude
    }));
    
    // Update path line
    this.pathLine.setPath(this.path);
    
    // Create bounds to fit all points
    const bounds = new google.maps.LatLngBounds();
    this.path.forEach(point => bounds.extend(point));
    
    // Add start marker (green)
    const startLocation = locations[0];
    const startMarker = new google.maps.Marker({
      position: { lat: startLocation.latitude, lng: startLocation.longitude },
      map: this.map,
      title: 'Trip Start',
      icon: {
        url: 'https://maps.google.com/mapfiles/ms/icons/green-dot.png'
      }
    });
    
    const startInfoWindow = new google.maps.InfoWindow({
      content: `
        <div>
          <strong>Trip Start</strong><br>
          Time: ${new Date(startLocation.timestamp).toLocaleString()}<br>
          ${startLocation.speed ? `Speed: ${(startLocation.speed * 3.6).toFixed(1)} km/h` : ''}
        </div>
      `
    });
    
    startMarker.addListener('click', () => {
      startInfoWindow.open(this.map, startMarker);
    });
    
    // Add end marker (red)
    const endLocation = locations[locations.length - 1];
    const endMarker = new google.maps.Marker({
      position: { lat: endLocation.latitude, lng: endLocation.longitude },
      map: this.map,
      title: 'Latest Position',
      icon: {
        url: 'https://maps.google.com/mapfiles/ms/icons/red-dot.png'
      }
    });
    
    const endInfoWindow = new google.maps.InfoWindow({
      content: `
        <div>
          <strong>Latest Position</strong><br>
          Time: ${new Date(endLocation.timestamp).toLocaleString()}<br>
          ${endLocation.speed ? `Speed: ${(endLocation.speed * 3.6).toFixed(1)} km/h` : ''}
        </div>
      `
    });
    
    endMarker.addListener('click', () => {
      endInfoWindow.open(this.map, endMarker);
    });
    
    // Add vehicle marker at latest position
    this.vehicleMarker = new google.maps.Marker({
      position: { lat: endLocation.latitude, lng: endLocation.longitude },
      map: this.map,
      title: 'Vehicle Current Position',
      icon: {
        url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(`
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M6 18L8 10H24L26 18V26H24V24H8V26H6V18Z" fill="#2563EB"/>
            <circle cx="10" cy="22" r="2" fill="#1F2937"/>
            <circle cx="22" cy="22" r="2" fill="#1F2937"/>
            <path d="M8 10L10 6H22L24 10" fill="#3B82F6"/>
          </svg>
        `),
        scaledSize: new google.maps.Size(32, 32),
        anchor: new google.maps.Point(16, 16)
      }
    });
    
    // Add intermediate markers if there are many points
    if (locations.length > 10) {
      const step = Math.ceil(locations.length / 10);
      for (let i = step; i < locations.length - step; i += step) {
        const location = locations[i];
        const marker = new google.maps.Marker({
          position: { lat: location.latitude, lng: location.longitude },
          map: this.map,
          title: 'Location Point',
          icon: {
            url: 'https://maps.google.com/mapfiles/ms/icons/blue-dot.png',
            scaledSize: new google.maps.Size(20, 20)
          }
        });
        
        const infoWindow = new google.maps.InfoWindow({
          content: `
            <div>
              <strong>Location Point</strong><br>
              Time: ${new Date(location.timestamp).toLocaleString()}<br>
              ${location.speed ? `Speed: ${(location.speed * 3.6).toFixed(1)} km/h` : ''}
            </div>
          `
        });
        
        marker.addListener('click', () => {
          infoWindow.open(this.map, marker);
        });
        
        this.markers.push(marker);
      }
    }
    
    // Fit map to show all markers
    this.map.fitBounds(bounds);
  }
  
  showMapError(message) {
    // Center the map
    this.map.setCenter({ lat: 0, lng: 0 });
    this.map.setZoom(2);
    
    // Show error info window
    const infoWindow = new google.maps.InfoWindow({
      content: `<div style="color: red;">${message}</div>`,
      position: { lat: 0, lng: 0 }
    });
    
    infoWindow.open(this.map);
  }
}