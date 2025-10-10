let map;
let floodLayer, landslideLayer, liquefactionLayer;
let currentMarker;
let facilityMarkers = L.layerGroup();

const COLORS = {
    'LS': '#10b981',   // Green - Low
    'MS': '#f59e0b',   // Yellow - Moderate
    'HS': '#f97316',   // Orange - High
    'VHS': '#ef4444',  // Red - Very High
    'DF': '#a855f7'    // Purple - Debris Flow (landslide only)
};

function initMap() {
    map = L.map('map', {
        zoomControl: false
    }).setView([9.3, 123.3], 9);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);

    // Create layer groups - only flood visible by default
    floodLayer = L.layerGroup().addTo(map);
    landslideLayer = L.layerGroup(); // Not added to map initially
    liquefactionLayer = L.layerGroup(); // Not added to map initially
    facilityMarkers.addTo(map);

    // Load all data upfront for instant toggling
    loadHazardData();
    
    map.on('click', function (e) {
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
            // Get color - defaults to gray if unknown code
            let fillColor = COLORS[susceptibility] || '#9ca3af';
            
            // Special styling for Debris Flow - make it more visible
            let fillOpacity = 0.6;
            if (susceptibility === 'DF') {
                fillOpacity = 0.7;  // Slightly more opaque for debris flow
            }
            
            return {
                fillColor: fillColor,
                weight: 0.5,
                opacity: 1,
                color: 'rgba(255,255,255,0.4)',
                fillOpacity: fillOpacity
            };
        },
        onEachFeature: function(feature, layer) {
            layer.on('click', function(e) {
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

async function showLocationInfo(lat, lng) {
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const locationInfo = document.getElementById('location-info');
    const hazardDetails = document.getElementById('hazard-details');

    sidebar.classList.remove('hidden');
    sidebarToggle.classList.add('sidebar-open');

    locationInfo.innerHTML = `
        <div style="text-align: center;">
            <p style="color: #6b7280; font-size: 0.875rem;">Loading location information...</p>
        </div>
    `;

    try {
        const response = await fetch(`/api/location-info/?lat=${lat}&lng=${lng}`);
        const locationData = await response.json();
        
        if (response.ok && locationData.success) {
            locationInfo.innerHTML = `
                <div style="text-align: left;">
                    <div style="margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 2px solid #e5e7eb;">
                        <div style="font-size: 1.1rem; font-weight: 700; color: #1f2937; margin-bottom: 0.25rem;">
                            ${locationData.barangay}
                        </div>
                        <div style="font-size: 0.95rem; color: #4b5563; margin-bottom: 0.25rem;">
                            ${locationData.municipality}, ${locationData.province}
                        </div>
                    </div>
                    <div style="font-size: 0.8rem; color: #6b7280;">
                        <div>Latitude: ${lat.toFixed(6)}</div>
                        <div>Longitude: ${lng.toFixed(6)}</div>
                    </div>
                </div>
            `;
        } else {
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
        }
    } catch (error) {
        console.error('Error fetching location info:', error);
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
    }

    getHazardInfoForLocation(lat, lng, hazardDetails);
    
    const facilitiesContainer = document.getElementById('facilities-section');
    if (facilitiesContainer) {
        loadNearbyFacilities(lat, lng);
    }
}

async function getHazardInfoForLocation(lat, lng, container) {
    container.innerHTML = '<p style="text-align: center; color: #6b7280; padding: 1rem;">Analyzing hazard levels...</p>';

    try {
        const response = await fetch(`/api/location-hazards/?lat=${lat}&lng=${lng}`);
        const data = await response.json();

        if (response.ok) {
            const overall = data.overall_risk;
            
            let html = `
                <!-- Overall Risk Assessment Card -->
                <div style="background: ${overall.color}15; border: 2px solid ${overall.color}; border-radius: 0.5rem; padding: 1rem; margin-bottom: 1.5rem;">
                    <div style="text-align: center; margin-bottom: 0.75rem;">
                        <span style="font-size: 2rem;">${overall.icon}</span>
                    </div>
                    <div style="text-align: center; font-size: 1.25rem; font-weight: 700; color: ${overall.color}; margin-bottom: 0.5rem;">
                        ${overall.category}
                    </div>
                    <div style="text-align: center; font-size: 0.875rem; color: #4b5563; margin-bottom: 0.75rem;">
                        ${overall.message}
                    </div>
                    <div style="background: white; border-radius: 0.375rem; padding: 0.75rem; margin-top: 0.75rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                            <span style="font-size: 0.75rem; color: #6b7280; font-weight: 600;">RISK SCORE</span>
                            <span style="font-size: 1.25rem; font-weight: 700; color: ${overall.color};">${overall.score}/100</span>
                        </div>
                        <div style="width: 100%; height: 8px; background: #e5e7eb; border-radius: 9999px; overflow: hidden;">
                            <div style="width: ${overall.score}%; height: 100%; background: ${overall.color}; transition: width 0.5s;"></div>
                        </div>
                    </div>
                    <div style="font-size: 0.8rem; color: #4b5563; margin-top: 0.75rem; padding: 0.625rem; background: white; border-radius: 0.375rem;">
                        <strong>Recommendation:</strong> ${overall.recommendation}
                    </div>
                </div>

                <!-- Individual Hazards (Collapsible) -->
                <details style="margin-bottom: 1rem;">
                    <summary style="cursor: pointer; font-weight: 600; color: #374151; padding: 0.75rem; background: #f9fafb; border-radius: 0.375rem; margin-bottom: 0.5rem;">
                        View Detailed Hazard Breakdown ▼
                    </summary>
                    <div class="hazard-item" style="margin-top: 0.75rem;">
            `;

            // Flood
            const floodColor = getColorForLevel(data.flood.level);
            html += `
                <div style="padding: 0.75rem 0; border-bottom: 1px solid #e5e7eb;">
                    <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                        <span style="display: inline-block; width: 20px; height: 20px; background-color: ${floodColor}; border: 1px solid rgba(0,0,0,0.1); border-radius: 0.25rem; margin-right: 0.75rem;"></span>
                        <strong style="flex: 1;">🌊 Flood Risk</strong>
                    </div>
                    <div style="margin-left: 2rem; font-size: 0.875rem; color: #6b7280;">
                        ${data.flood.risk_label}
                    </div>
                </div>
            `;

            // Landslide
            const landslideColor = getColorForLevel(data.landslide.level);
            const landslideIcon = data.landslide.level === 'DF' ? '🌋' : '⛰️';
            const landslideLabel = data.landslide.level === 'DF' ? 'Debris Flow Risk' : 'Landslide Risk';
            html += `
                <div style="padding: 0.75rem 0; border-bottom: 1px solid #e5e7eb;">
                    <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                        <span style="display: inline-block; width: 20px; height: 20px; background-color: ${landslideColor}; border: 1px solid rgba(0,0,0,0.1); border-radius: 0.25rem; margin-right: 0.75rem;"></span>
                        <strong style="flex: 1;">${landslideIcon} ${landslideLabel}</strong>
                    </div>
                    <div style="margin-left: 2rem; font-size: 0.875rem; color: #6b7280;">
                        ${data.landslide.risk_label}
                    </div>
                </div>
            `;

            // Liquefaction
            const liquefactionColor = getColorForLevel(data.liquefaction.level);
            html += `
                <div style="padding: 0.75rem 0;">
                    <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                        <span style="display: inline-block; width: 20px; height: 20px; background-color: ${liquefactionColor}; border: 1px solid rgba(0,0,0,0.1); border-radius: 0.25rem; margin-right: 0.75rem;"></span>
                        <strong style="flex: 1;">〰️ Ground Shaking Risk</strong>
                    </div>
                    <div style="margin-left: 2rem; font-size: 0.875rem; color: #6b7280;">
                        ${data.liquefaction.risk_label}
                    </div>
                </div>
            `;

            html += `
                    </div>
                </details>
            `;

            container.innerHTML = html;
        } else {
            container.innerHTML = `<p style="color: #ef4444; padding: 1rem; text-align: center;">Error: ${data.error || 'Unable to retrieve hazard information'}</p>`;
        }
    } catch (error) {
        container.innerHTML = '<p style="color: #ef4444; padding: 1rem; text-align: center;">Error retrieving hazard information</p>';
        console.error('Error getting hazard info:', error);
    }
}

function getColorForLevel(level) {
    if (!level) return '#10b981';  // No data = GREEN (safe zone)
    return COLORS[level] || '#9ca3af';
}

// Custom Zoom Controls
function setupCustomZoomControls() {
    const zoomInBtn = document.getElementById('zoom-in-btn');
    const zoomOutBtn = document.getElementById('zoom-out-btn');

    zoomInBtn.addEventListener('click', function() {
        map.zoomIn();
    });

    zoomOutBtn.addEventListener('click', function() {
        map.zoomOut();
    });
}

// Layer Control Panel
// Layer Control Panel
function setupLayerControl() {
    const layerControlBtn = document.getElementById('layer-control-btn');
    const layerPanel = document.getElementById('layer-panel');
    const closeLayerPanel = document.getElementById('close-layer-panel');

    layerControlBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        layerPanel.classList.toggle('hidden');
    });

    closeLayerPanel.addEventListener('click', function() {
        layerPanel.classList.add('hidden');
    });

    // Close panel when clicking outside
    document.addEventListener('click', function(e) {
        if (!layerPanel.contains(e.target) && !layerControlBtn.contains(e.target)) {
            layerPanel.classList.add('hidden');
        }
    });
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

// Legend Controls
function setupLegendControls() {
    const legend = document.getElementById('legend');
    const legendToggle = document.getElementById('legend-toggle');
    const closeLegend = document.getElementById('close-legend');

    closeLegend.addEventListener('click', function() {
        legend.classList.add('hidden');
        legendToggle.classList.remove('hidden');
    });

    legendToggle.addEventListener('click', function() {
        legend.classList.remove('hidden');
        legendToggle.classList.add('hidden');
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
        const response = await fetch(
            `https://nominatim.openstreetmap.org/search?` +
            `format=json&q=${encodeURIComponent(searchTerm + ', Negros Oriental, Philippines')}&limit=5`
        );
        
        const results = await response.json();
        
        if (results.length > 0) {
            const lat = parseFloat(results[0].lat);
            const lng = parseFloat(results[0].lon);
            
            map.setView([lat, lng], 15);
            
            if (currentMarker) {
                map.removeLayer(currentMarker);
            }
            
            currentMarker = L.marker([lat, lng]).addTo(map);
            showLocationInfo(lat, lng);
        } else {
            alert('Location not found. Try: "Dumaguete", "Bais", or a barangay name');
        }
        
    } catch (error) {
        console.error('Search error:', error);
        alert('Error searching for location');
    }
}

async function loadNearbyFacilities(lat, lng) {
    const container = document.getElementById('facilities-section');
    container.innerHTML = '<p style="text-align: center; color: #6b7280; padding: 1rem;">Loading nearby facilities from OpenStreetMap...</p>';
    
    try {
        const response = await fetch(`/api/nearby-facilities/?lat=${lat}&lng=${lng}&radius=3000`);
        
        if (!response.ok) {
            throw new Error('Failed to fetch facilities');
        }
        
        const data = await response.json();
        displayFacilities(data);
        
    } catch (error) {
        console.error('Error loading facilities:', error);
        container.innerHTML = '<p style="color: #ef4444; padding: 1rem; text-align: center;">Error loading facilities. Please try again.</p>';
    }
}

function displayFacilities(data) {
    const container = document.getElementById('facilities-section');
    
    facilityMarkers.clearLayers();
    
    if (data.counts.total === 0) {
        container.innerHTML = `
            <div style="padding: 1rem; background: #fef3c7; border: 1px solid #fbbf24; border-radius: 0.5rem; text-align: center;">
                <p style="margin: 0; color: #92400e;">No facilities found within 3km radius</p>
            </div>
        `;
        return;
    }
    
    let html = `
        <!-- Emergency Readiness Summary -->
        <div style="background: #f0f9ff; border: 1px solid #bfdbfe; border-radius: 0.5rem; padding: 1rem; margin-bottom: 1.5rem;">
            <h5 style="margin: 0 0 0.75rem 0; color: #1e40af; font-size: 0.95rem; font-weight: 700;">
                🚨 Emergency Preparedness
            </h5>
    `;
    
    // Nearest Evacuation
    if (data.summary.nearest_evacuation) {
        const evac = data.summary.nearest_evacuation;
        const walkIcon = evac.is_walkable ? '✅' : '⚠️';
        html += `
            <div style="margin-bottom: 0.5rem; padding: 0.5rem; background: white; border-radius: 0.375rem;">
                <div style="font-size: 0.8rem; color: #6b7280; margin-bottom: 0.25rem;">Nearest Evacuation Center:</div>
                <div style="font-weight: 600; color: #1f2937; font-size: 0.875rem;">${walkIcon} ${evac.name}</div>
                <div style="font-size: 0.8rem; color: #059669; font-weight: 600;">${evac.distance} away</div>
            </div>
        `;
    } else {
        html += `
            <div style="padding: 0.75rem; background: #fee2e2; border-radius: 0.375rem; margin-bottom: 0.5rem;">
                <div style="color: #991b1b; font-size: 0.875rem; font-weight: 600;">⚠️ No evacuation center within 3km</div>
            </div>
        `;
    }
    
    // Nearest Hospital
    if (data.summary.nearest_hospital) {
        const hosp = data.summary.nearest_hospital;
        const walkIcon = hosp.is_walkable ? '✅' : '⚠️';
        html += `
            <div style="margin-bottom: 0.5rem; padding: 0.5rem; background: white; border-radius: 0.375rem;">
                <div style="font-size: 0.8rem; color: #6b7280; margin-bottom: 0.25rem;">Nearest Medical Facility:</div>
                <div style="font-weight: 600; color: #1f2937; font-size: 0.875rem;">${walkIcon} ${hosp.name}</div>
                <div style="font-size: 0.8rem; color: #059669; font-weight: 600;">${hosp.distance} away</div>
            </div>
        `;
    }
    
    html += `
            <div style="font-size: 0.75rem; color: #6b7280; margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid #bfdbfe;">
                ✅ = Within 500m walking distance
            </div>
        </div>
    `;
    
    // Detailed Facility Lists (Collapsible)
    if (data.evacuation_centers.length > 0) {
        html += `
            <details style="margin-bottom: 1rem;">
                <summary style="cursor: pointer; font-weight: 600; color: #dc2626; padding: 0.75rem; background: #fee2e2; border-radius: 0.375rem;">
                    🏠 Evacuation Centers (${data.counts.evacuation}) ▼
                </summary>
                <div style="margin-top: 0.5rem;">
        `;
        data.evacuation_centers.forEach((f, index) => {
            html += createFacilityCard(f, '#dc2626', '#fef2f2', `evac-${index}`);
            addFacilityMarker(f, '#dc2626');
        });
        html += `</div></details>`;
    }
    
    if (data.medical.length > 0) {
        html += `
            <details style="margin-bottom: 1rem;">
                <summary style="cursor: pointer; font-weight: 600; color: #dc2626; padding: 0.75rem; background: #fee2e2; border-radius: 0.375rem;">
                    🏥 Medical Facilities (${data.counts.medical}) ▼
                </summary>
                <div style="margin-top: 0.5rem;">
        `;
        data.medical.forEach((f, index) => {
            html += createFacilityCard(f, '#dc2626', '#fef2f2', `medical-${index}`);
            addFacilityMarker(f, '#dc2626');
        });
        html += `</div></details>`;
    }
    
    if (data.emergency_services.length > 0) {
        html += `
            <details style="margin-bottom: 1rem;">
                <summary style="cursor: pointer; font-weight: 600; color: #dc2626; padding: 0.75rem; background: #fee2e2; border-radius: 0.375rem;">
                    🚒 Emergency Services (${data.counts.emergency_services}) ▼
                </summary>
                <div style="margin-top: 0.5rem;">
        `;
        data.emergency_services.forEach((f, index) => {
            html += createFacilityCard(f, '#dc2626', '#fef2f2', `emergency-${index}`);
            addFacilityMarker(f, '#dc2626');
        });
        html += `</div></details>`;
    }
    
    if (data.essential_services.length > 0) {
        html += `
            <details style="margin-bottom: 1rem;">
                <summary style="cursor: pointer; font-weight: 600; color: #2563eb; padding: 0.75rem; background: #dbeafe; border-radius: 0.375rem;">
                    🛒 Essential Services (${data.counts.essential}) ▼
                </summary>
                <div style="margin-top: 0.5rem;">
        `;
        data.essential_services.forEach((f, index) => {
            html += createFacilityCard(f, '#2563eb', '#eff6ff', `essential-${index}`);
            addFacilityMarker(f, '#2563eb');
        });
        html += `</div></details>`;
    }
    
    html += `
        <div style="margin-top: 1rem; padding: 0.75rem; background: #f9fafb; border-radius: 0.5rem; text-align: center;">
            <p style="margin: 0; font-size: 0.75rem; color: #6b7280;">
                Data from OpenStreetMap contributors
            </p>
        </div>
    `;
    
    container.innerHTML = html;
    attachFacilityClickListeners();
}

function createFacilityCard(facility, borderColor, bgColor, facilityId) {
    return `
        <div class="facility-card" data-facility-id="${facilityId}" data-lat="${facility.lat}" data-lng="${facility.lng}" 
             style="padding: 0.75rem; border-left: 3px solid ${borderColor}; margin-bottom: 0.5rem; background: ${bgColor}; 
                    border-radius: 0 0.25rem 0.25rem 0; cursor: pointer; transition: all 0.2s;"
             onmouseover="this.style.backgroundColor='${adjustColor(bgColor, -10)}'; this.style.transform='translateX(4px)';"
             onmouseout="this.style.backgroundColor='${bgColor}'; this.style.transform='translateX(0)';">
            <div style="font-weight: 600; font-size: 0.875rem; color: #1f2937; margin-bottom: 0.25rem;">
                ${facility.name}
            </div>
            <div style="font-size: 0.8rem; color: #6b7280;">
                ${facility.type_display}
            </div>
            <div style="font-size: 0.8rem; color: #059669; font-weight: 600; margin-top: 0.25rem;">
                ${facility.distance_display} away
            </div>
            <div style="font-size: 0.75rem; color: #3b82f6; margin-top: 0.25rem; font-style: italic;">
                Click to view on map
            </div>
        </div>
    `;
}

function addFacilityMarker(facility, color) {
    const icon = L.divIcon({
        className: 'custom-facility-marker',
        html: `<div style="background-color: ${color}; width: 12px; height: 12px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>`,
        iconSize: [12, 12],
        iconAnchor: [6, 6]
    });
    
    const marker = L.marker([facility.lat, facility.lng], { icon: icon })
        .bindPopup(`
            <div style="min-width: 150px;">
                <strong style="display: block; margin-bottom: 0.5rem;">${facility.name}</strong>
                <div style="font-size: 0.85rem; color: #6b7280;">${facility.type_display}</div>
                <div style="font-size: 0.85rem; color: #059669; font-weight: 600; margin-top: 0.25rem;">
                    ${facility.distance_display} away
                </div>
            </div>
        `);
    
    facilityMarkers.addLayer(marker);
}

function attachFacilityClickListeners() {
    const facilityCards = document.querySelectorAll('.facility-card');
    
    facilityCards.forEach(card => {
        card.addEventListener('click', function() {
            const lat = parseFloat(this.dataset.lat);
            const lng = parseFloat(this.dataset.lng);
            
            map.setView([lat, lng], 17, {
                animate: true,
                duration: 0.5
            });
            
            facilityMarkers.eachLayer(layer => {
                if (layer instanceof L.Marker) {
                    const markerLatLng = layer.getLatLng();
                    if (Math.abs(markerLatLng.lat - lat) < 0.00001 && 
                        Math.abs(markerLatLng.lng - lng) < 0.00001) {
                        layer.openPopup();
                    }
                }
            });
        });
    });
}

function adjustColor(color, amount) {
    return color.replace(/^#/, '')
        .match(/.{2}/g)
        .map(hex => {
            const num = parseInt(hex, 16) + amount;
            return Math.max(0, Math.min(255, num)).toString(16).padStart(2, '0');
        })
        .reduce((str, hex) => str + hex, '#');
}

// Initialize everything when DOM is ready
document.addEventListener('DOMContentLoaded', function () {
    initMap();
    setupCustomZoomControls();
    setupLayerControl();
    setupSidebarControls();
    setupLegendControls();
    setupLayerToggles();
    setupUploadModal();
    setupSearch();
});