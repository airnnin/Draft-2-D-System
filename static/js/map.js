let map;
let floodLayer, landslideLayer, liquefactionLayer;
let currentMarker;

const COLORS = {
    'LS': '#10b981',
    'MS': '#f59e0b',
    'HS': '#f97316',
    'VHS': '#ef4444'
};

function initMap() {
    map = L.map('map').setView([9.3, 123.3], 9);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);

    floodLayer = L.layerGroup().addTo(map);
    landslideLayer = L.layerGroup().addTo(map);
    liquefactionLayer = L.layerGroup().addTo(map);

    loadHazardData();

    // Map click - only trigger when not clicking on a polygon
    map.on('click', function (e) {
        // Check if click was on the map itself, not a feature
        if (!e.originalEvent.defaultPrevented) {
            onMapClick(e);
        }
    });
}

async function loadHazardData() {
    try {
        const floodResponse = await fetch('/api/flood-data/');
        if (floodResponse.ok) {
            const floodData = await floodResponse.json();
            addGeoJSONLayer(floodData, floodLayer, 'flood');
        }

        const landslideResponse = await fetch('/api/landslide-data/');
        if (landslideResponse.ok) {
            const landslideData = await landslideResponse.json();
            addGeoJSONLayer(landslideData, landslideLayer, 'landslide');
        }

        const liquefactionResponse = await fetch('/api/liquefaction-data/');
        if (liquefactionResponse.ok) {
            const liquefactionData = await liquefactionResponse.json();
            addGeoJSONLayer(liquefactionData, liquefactionLayer, 'liquefaction');
        }
    } catch (error) {
        console.error('Error loading hazard data:', error);
    }
}

function addGeoJSONLayer(geojsonData, layerGroup, hazardType) {
    L.geoJSON(geojsonData, {
        style: function(feature) {
            const susceptibility = feature.properties.susceptibility;
            return {
                fillColor: COLORS[susceptibility] || '#9ca3af',
                weight: 0.5,
                opacity: 1,
                color: 'rgba(255,255,255,0.4)',
                fillOpacity: 0.6
            };
        },
        onEachFeature: function(feature, layer) {
            // Remove popup binding - polygons are now just visual layers
            // Clicking them will place the pin instead
            
            // Make polygon clicks pass through to the map
            layer.on('click', function(e) {
                // Don't stop propagation - let the click pass through to map
                // This allows pin placement on polygons
                onMapClick(e);
            });
            
            layer.addTo(layerGroup);
        }
    });
}

function onMapClick(e) {
    const lat = e.latlng.lat;
    const lng = e.latlng.lng;

    if (currentMarker) {
        map.removeLayer(currentMarker);
    }

    currentMarker = L.marker([lat, lng]).addTo(map);
    showLocationInfo(lat, lng);
}

function showLocationInfo(lat, lng) {
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const locationInfo = document.getElementById('location-info');
    const hazardDetails = document.getElementById('hazard-details');

    // Show sidebar
    sidebar.classList.remove('hidden');
    sidebarToggle.classList.add('sidebar-open');

    locationInfo.innerHTML = `
        <div style="text-align: left;">
            <strong style="color: #1f2937; font-size: 0.95rem; display: block; margin-bottom: 0.5rem;">
                Selected Location
            </strong>
            <span style="color: #6b7280; font-size: 0.875rem; display: block;">
                Latitude: ${lat.toFixed(6)}
            </span>
            <span style="color: #6b7280; font-size: 0.875rem; display: block;">
                Longitude: ${lng.toFixed(6)}
            </span>
        </div>
    `;

    getHazardInfoForLocation(lat, lng, hazardDetails);
}

async function getHazardInfoForLocation(lat, lng, container) {
    container.innerHTML = '<p style="text-align: center; color: #6b7280; padding: 1rem;">Analyzing hazard levels...</p>';

    try {
        const response = await fetch(`/api/location-hazards/?lat=${lat}&lng=${lng}`);
        const data = await response.json();

        if (response.ok) {
            const hazardInfo = [];

            hazardInfo.push('<div class="hazard-item">');

            const floodColor = getColorForLevel(data.flood.level);
            hazardInfo.push(`
                <div>
                    <strong>Flood Susceptibility:</strong>
                    <div style="display: flex; align-items: center; margin-top: 0.375rem;">
                        <span style="display: inline-block; width: 16px; height: 16px; background-color: ${floodColor}; border: 1px solid rgba(0,0,0,0.1); border-radius: 0.25rem; margin-right: 0.5rem;"></span>
                        <span>${data.flood.label}</span>
                    </div>
                </div>
            `);

            const landslideColor = getColorForLevel(data.landslide.level);
            hazardInfo.push(`
                <div>
                    <strong>Landslide Susceptibility:</strong>
                    <div style="display: flex; align-items: center; margin-top: 0.375rem;">
                        <span style="display: inline-block; width: 16px; height: 16px; background-color: ${landslideColor}; border: 1px solid rgba(0,0,0,0.1); border-radius: 0.25rem; margin-right: 0.5rem;"></span>
                        <span>${data.landslide.label}</span>
                    </div>
                </div>
            `);

            const liquefactionColor = getColorForLevel(data.liquefaction.level);
            hazardInfo.push(`
                <div>
                    <strong>Liquefaction Susceptibility:</strong>
                    <div style="display: flex; align-items: center; margin-top: 0.375rem;">
                        <span style="display: inline-block; width: 16px; height: 16px; background-color: ${liquefactionColor}; border: 1px solid rgba(0,0,0,0.1); border-radius: 0.25rem; margin-right: 0.5rem;"></span>
                        <span>${data.liquefaction.label}</span>
                    </div>
                </div>
            `);

            hazardInfo.push('</div>');

            container.innerHTML = hazardInfo.join('');
        } else {
            container.innerHTML = `<p style="color: #ef4444; padding: 1rem; text-align: center;">Error: ${data.error || 'Unable to retrieve hazard information'}</p>`;
        }
    } catch (error) {
        container.innerHTML = '<p style="color: #ef4444; padding: 1rem; text-align: center;">Error retrieving hazard information</p>';
        console.error('Error getting hazard info:', error);
    }
}

function getColorForLevel(level) {
    if (!level) return '#9ca3af';
    return COLORS[level] || '#9ca3af';
}

// Sidebar controls
function setupSidebarControls() {
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebarClose = document.getElementById('sidebar-close');

    sidebarToggle.addEventListener('click', function () {
        sidebar.classList.toggle('hidden');
        sidebarToggle.classList.toggle('sidebar-open');
    });

    sidebarClose.addEventListener('click', function () {
        sidebar.classList.add('hidden');
        sidebarToggle.classList.remove('sidebar-open');
    });
}

function setupLayerToggles() {
    document.getElementById('flood-toggle').addEventListener('change', function (e) {
        if (e.target.checked) {
            map.addLayer(floodLayer);
        } else {
            map.removeLayer(floodLayer);
        }
    });

    document.getElementById('landslide-toggle').addEventListener('change', function (e) {
        if (e.target.checked) {
            map.addLayer(landslideLayer);
        } else {
            map.removeLayer(landslideLayer);
        }
    });

    document.getElementById('liquefaction-toggle').addEventListener('change', function (e) {
        if (e.target.checked) {
            map.addLayer(liquefactionLayer);
        } else {
            map.removeLayer(liquefactionLayer);
        }
    });
}

function setupUploadModal() {
    const uploadBtn = document.getElementById('upload-btn');
    const modal = document.getElementById('upload-modal');
    const closeBtn = document.getElementById('close-modal');
    const cancelBtn = document.getElementById('cancel-upload');
    const uploadForm = document.getElementById('upload-form');

    uploadBtn.addEventListener('click', () => {
        modal.classList.remove('hidden');
    });

    closeBtn.addEventListener('click', () => {
        modal.classList.add('hidden');
        resetUploadForm();
    });

    cancelBtn.addEventListener('click', () => {
        modal.classList.add('hidden');
        resetUploadForm();
    });

    // Close modal when clicking outside
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.add('hidden');
            resetUploadForm();
        }
    });

    uploadForm.addEventListener('submit', handleFileUpload);
}

async function handleFileUpload(e) {
    e.preventDefault();

    const formData = new FormData();
    const fileInput = document.getElementById('shapefile-input');
    const datasetType = document.getElementById('dataset-type').value;

    if (!fileInput.files[0]) {
        alert('Please select a shapefile to upload');
        return;
    }

    if (!datasetType) {
        alert('Please select a dataset type');
        return;
    }

    formData.append('shapefile', fileInput.files[0]);
    formData.append('dataset_type', datasetType);

    showUploadProgress();

    try {
        const response = await fetch('/api/upload-shapefile/', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (response.ok) {
            showUploadResult(true, `Successfully processed ${result.records_created} records`);
            setTimeout(() => {
                location.reload();
            }, 2000);
        } else {
            showUploadResult(false, result.error || 'Upload failed');
        }
    } catch (error) {
        showUploadResult(false, 'Network error occurred');
        console.error('Upload error:', error);
    }
}

function showUploadProgress() {
    document.getElementById('upload-form').classList.add('hidden');
    document.getElementById('upload-progress').classList.remove('hidden');
}

function showUploadResult(success, message) {
    document.getElementById('upload-progress').classList.add('hidden');
    const resultDiv = document.getElementById('upload-result');
    const messageDiv = document.getElementById('result-message');

    resultDiv.classList.remove('hidden');
    messageDiv.innerHTML = `
        <div style="padding: 1rem; border-radius: 0.5rem; ${success
            ? 'background: #d1fae5; color: #065f46; border: 1px solid #6ee7b7;'
            : 'background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5;'}">
            ${message}
        </div>
    `;
}

function resetUploadForm() {
    document.getElementById('upload-form').classList.remove('hidden');
    document.getElementById('upload-progress').classList.add('hidden');
    document.getElementById('upload-result').classList.add('hidden');
    document.getElementById('upload-form').reset();
}

function setupSearch() {
    const searchBtn = document.getElementById('search-btn');
    const searchInput = document.getElementById('location-search');

    searchBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
            performSearch();
        }
    });
}

async function performSearch() {
    const searchTerm = document.getElementById('location-search').value.trim();
    
    if (!searchTerm) {
        alert('Please enter a location to search');
        return;
    }
    
    try {
        // Use Nominatim for free geocoding
        const response = await fetch(
            `https://nominatim.openstreetmap.org/search?` +
            `format=json&q=${encodeURIComponent(searchTerm + ', Negros Oriental, Philippines')}&limit=5`
        );
        
        const results = await response.json();
        
        if (results.length > 0) {
            const lat = parseFloat(results[0].lat);
            const lng = parseFloat(results[0].lon);
            
            // Zoom to location
            map.setView([lat, lng], 15);
            
            // Remove existing marker
            if (currentMarker) {
                map.removeLayer(currentMarker);
            }
            
            // Add marker
            currentMarker = L.marker([lat, lng]).addTo(map);
            
            // Show info
            showLocationInfo(lat, lng);
        } else {
            alert('Location not found. Try: "Dumaguete", "Bais", or a barangay name');
        }
        
    } catch (error) {
        console.error('Search error:', error);
        alert('Error searching for location');
    }
}

document.addEventListener('DOMContentLoaded', function () {
    initMap();
    setupSidebarControls();
    setupLayerToggles();
    setupUploadModal();
    setupSearch();
});
