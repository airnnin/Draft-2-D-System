from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.gis.geos import Point
from .models import HazardDataset, FloodSusceptibility, LandslideSusceptibility, LiquefactionSusceptibility
from .utils import ShapefileProcessor
from .overpass_client import OverpassClient
from math import radians, cos, sin, asin, sqrt
import json

def index(request):
    """Main map view"""
    return render(request, 'index.html')

@csrf_exempt
@api_view(['POST'])
def upload_shapefile(request):
    """Handle shapefile upload and processing"""
    if request.method == 'POST':
        if 'shapefile' not in request.FILES:
            return JsonResponse({'error': 'No shapefile provided'}, status=400)
        
        if 'dataset_type' not in request.POST:
            return JsonResponse({'error': 'Dataset type not specified'}, status=400)
        
        uploaded_file = request.FILES['shapefile']
        dataset_type = request.POST['dataset_type']
        
        valid_types = ['flood', 'landslide', 'liquefaction']
        if dataset_type not in valid_types:
            return JsonResponse({'error': f'Invalid dataset type. Must be one of: {valid_types}'}, status=400)
        
        processor = ShapefileProcessor(uploaded_file, dataset_type)
        result = processor.process()
        
        if result['success']:
            return JsonResponse(result)
        else:
            return JsonResponse({'error': result['error']}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@api_view(['GET'])
def get_flood_data(request):
    """Get flood susceptibility data as GeoJSON"""
    try:
        flood_features = []
        flood_records = FloodSusceptibility.objects.all()
        
        for record in flood_records:
            feature = {
                'type': 'Feature',
                'properties': {
                    'susceptibility': record.flood_susc,
                    'original_code': record.original_code,
                    'shape_area': record.shape_area,
                    'dataset_id': record.dataset.id
                },
                'geometry': json.loads(record.geometry.geojson)
            }
            flood_features.append(feature)
        
        geojson_data = {
            'type': 'FeatureCollection',
            'features': flood_features
        }
        
        return Response(geojson_data)
    
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
def get_landslide_data(request):
    """Get landslide susceptibility data as GeoJSON"""
    try:
        landslide_features = []
        landslide_records = LandslideSusceptibility.objects.all()
        
        for record in landslide_records:
            feature = {
                'type': 'Feature',
                'properties': {
                    'susceptibility': record.landslide_susc,
                    'original_code': record.original_code,
                    'shape_area': record.shape_area,
                    'dataset_id': record.dataset.id
                },
                'geometry': json.loads(record.geometry.geojson)
            }
            landslide_features.append(feature)
        
        geojson_data = {
            'type': 'FeatureCollection',
            'features': landslide_features
        }
        
        return Response(geojson_data)
    
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
def get_liquefaction_data(request):
    """Get liquefaction susceptibility data as GeoJSON"""
    try:
        liquefaction_features = []
        liquefaction_records = LiquefactionSusceptibility.objects.all()
        
        for record in liquefaction_records:
            feature = {
                'type': 'Feature',
                'properties': {
                    'susceptibility': record.liquefaction_susc,
                    'original_code': record.original_code,
                    'dataset_id': record.dataset.id
                },
                'geometry': json.loads(record.geometry.geojson)
            }
            liquefaction_features.append(feature)
        
        geojson_data = {
            'type': 'FeatureCollection',
            'features': liquefaction_features
        }
        
        return Response(geojson_data)
    
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
def get_location_hazards(request):
    """Get hazard levels for a specific point location"""
    try:
        lat = float(request.GET.get('lat'))
        lng = float(request.GET.get('lng'))
        
        point = Point(lng, lat, srid=4326)
        
        flood_result = FloodSusceptibility.objects.filter(
            geometry__contains=point
        ).first()
        
        landslide_result = LandslideSusceptibility.objects.filter(
            geometry__contains=point
        ).first()
        
        liquefaction_result = LiquefactionSusceptibility.objects.filter(
            geometry__contains=point
        ).first()
        
        # Extract levels
        flood_level = flood_result.flood_susc if flood_result else None
        landslide_level = landslide_result.landslide_susc if landslide_result else None
        liquefaction_level = liquefaction_result.liquefaction_susc if liquefaction_result else None
        
        # Calculate overall risk
        risk_assessment = calculate_risk_score(flood_level, landslide_level, liquefaction_level)
        
        return Response({
            'overall_risk': risk_assessment,
            'flood': {
                'level': flood_level,
                'label': flood_result.get_flood_susc_display() if flood_result else 'No Data Available',
                'risk_label': get_user_friendly_label(flood_level, 'flood')
            },
            'landslide': {
                'level': landslide_level,
                'label': landslide_result.get_landslide_susc_display() if landslide_result else 'No Data Available',
                'risk_label': get_user_friendly_label(landslide_level, 'landslide')
            },
            'liquefaction': {
                'level': liquefaction_level,
                'label': liquefaction_result.get_liquefaction_susc_display() if liquefaction_result else 'No Data Available',
                'risk_label': get_user_friendly_label(liquefaction_level, 'liquefaction')
            }
        })
        
    except ValueError:
        return Response({'error': 'Invalid coordinates'}, status=400)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

def get_user_friendly_label(level, hazard_type):
    """Convert technical labels to citizen-friendly descriptions"""
    if not level:
        return 'Not at risk - No hazard data for this area (safe zone)'
    
    DESCRIPTIONS = {
        'flood': {
            'LS': 'Low risk - Flooding unlikely in this area',
            'MS': 'Moderate risk - Minor flooding possible during heavy rain',
            'HS': 'High risk - Frequent flooding expected during typhoons',
            'VHS': 'Very high risk - Severe flooding likely, area may become submerged'
        },
        'landslide': {
            'LS': 'Low risk - Stable ground, slopes are secure',
            'MS': 'Moderate risk - Some slope movement possible during heavy rain',
            'HS': 'High risk - Slopes may collapse during typhoons or earthquakes',
            'VHS': 'Very high risk - Steep unstable slopes, landslides expected during storms',
            'DF': 'CRITICAL RISK - Debris Flow Zone: Massive fast-moving landslides carrying rocks, mud, and debris. Extremely dangerous during heavy rain. EVACUATION REQUIRED.'
        },
        'liquefaction': {
            'LS': 'Low risk - Soil remains stable during earthquakes',
            'MS': 'Moderate risk - During strong earthquakes, ground may shift slightly',
            'HS': 'High risk - During earthquakes, ground may turn soft like quicksand, causing buildings to sink or tilt'
        }
    }
    
    return DESCRIPTIONS.get(hazard_type, {}).get(level, 'Risk level unknown')

def calculate_risk_score(flood_level, landslide_level, liquefaction_level):
    """
    Calculate overall risk score with proper debris flow handling
    and dynamic risk-specific recommendations
    """
    # Risk weights based on Philippine disaster frequency
    WEIGHTS = {
        'flood': 0.5,      # 50% - most frequent disaster
        'landslide': 0.3,  # 30% - common in mountainous areas
        'liquefaction': 0.2 # 20% - only during earthquakes
    }
    
    # Base scores (normalized to 100)
    LEVEL_SCORES = {
        'LS': 25,   # Low = 25/100
        'MS': 50,   # Moderate = 50/100
        'HS': 75,   # High = 75/100
        'VHS': 100, # Very High = 100/100
        'DF': 100,  # Debris Flow = 100/100 (base score same as VHS)
        None: 10    # NO DATA = 10/100 (assume safe - no hazard present)
    }
    
    # Calculate weighted scores
    flood_score = LEVEL_SCORES.get(flood_level, 10) * WEIGHTS['flood']
    landslide_score = LEVEL_SCORES.get(landslide_level, 10) * WEIGHTS['landslide']
    liquefaction_score = LEVEL_SCORES.get(liquefaction_level, 10) * WEIGHTS['liquefaction']
    
    # FIXED: Apply debris flow severity multiplier (1.5x more severe than VHS)
    if landslide_level == 'DF':
        landslide_score *= 1.5  # 100 * 0.3 * 1.5 = 45 points (vs VHS flood's 50)
    
    total_score = flood_score + landslide_score + liquefaction_score
    
    # Categorize overall risk
    if total_score < 25:
        category = 'LOW RISK'
        message = 'Generally safe for development'
        color = '#10b981'  # Green
        icon = '✅'
        safety_level = 'SAFE'
    elif total_score < 50:
        category = 'MODERATE RISK'
        message = 'Acceptable with precautions'
        color = '#f59e0b'  # Yellow
        icon = '⚠️'
        safety_level = 'CAUTION'
    elif total_score < 75:
        category = 'HIGH RISK'
        message = 'Significant hazards present'
        color = '#f97316'  # Orange
        icon = '⚠️'
        safety_level = 'WARNING'
    else:
        category = 'VERY HIGH RISK'
        message = 'Not recommended for development'
        color = '#ef4444'  # Red
        icon = '🚫'
        safety_level = 'DANGER'
    
    # IMPROVED: Generate risk-specific recommendations    
    rec_data = generate_smart_recommendations(flood_level, landslide_level, liquefaction_level)

    return {
            'score': round(min(total_score, 100), 1),
            'raw_score': round(total_score, 1),
            'category': category,
            'message': message,
            'color': color,
            'icon': icon,
            'recommendation_summary': rec_data['summary'],  # For button label
            'recommendation_details': rec_data['details'],  # Collapsible content
            'safety_level': safety_level
    }


def generate_smart_recommendations(flood_level, landslide_level, liquefaction_level):
    """
    Generate recommendations based on Philippine government guidelines:
    - PHIVOLCS (Philippine Institute of Volcanology and Seismology)
    - PAGASA (Philippine Atmospheric, Geophysical and Astronomical Services Administration)
    - DPWH (Department of Public Works and Highways)
    - National Building Code (PD 1096)
    - National Structural Code of the Philippines (NSCP)
    """
    high_risks = []
    
    # Identify high risks
    if flood_level in ['HS', 'VHS']:
        high_risks.append('flood')
    if landslide_level in ['HS', 'VHS', 'DF']:
        high_risks.append('landslide')
    if liquefaction_level in ['HS']:
        high_risks.append('liquefaction')
    
    # LOW/MODERATE RISK - Return simple recommendations
    if not high_risks:
        if flood_level == 'MS' or landslide_level == 'MS' or liquefaction_level == 'MS':
            return {
                'summary': 'Standard building codes with enhanced precautions',
                'details': '''
                    <div style="padding: 1rem; line-height: 1.8;">
                        <p style="margin-bottom: 1rem;"><strong>This location is suitable for development with standard precautions:</strong></p>
                        <ul style="margin: 0 0 1rem 1.5rem;">
                            <li><strong>Building Code Compliance:</strong> Follow National Building Code of the Philippines (PD 1096)</li>
                            <li><strong>Site Assessment:</strong> Conduct geotechnical investigation before construction</li>
                            <li><strong>Drainage Systems:</strong> Install proper surface water drainage</li>
                            <li><strong>Slope Protection:</strong> Maintain vegetation on slopes</li>
                        </ul>
                        <div style="background: #dbeafe; padding: 0.75rem; border-radius: 6px; border-left: 3px solid #3b82f6; margin-top: 1rem;">
                            <strong style="color: #1e40af;">📋 Required Permits:</strong><br>
                            Secure Building Permit from Local Government Unit and consult licensed civil/structural engineer.
                        </div>
                    </div>
                '''
            }
        else:
            return {
                'summary': 'Low risk - Standard construction practices',
                'details': '''
                    <div style="padding: 1rem; line-height: 1.8;">
                        <p style="margin-bottom: 1rem;"><strong>This location has minimal disaster exposure:</strong></p>
                        <ul style="margin: 0 0 1rem 1.5rem;">
                            <li><strong>Standard Building Code:</strong> Comply with National Building Code (PD 1096)</li>
                            <li><strong>Regular Maintenance:</strong> Maintain drainage and building integrity</li>
                            <li><strong>Emergency Preparedness:</strong> Prepare basic evacuation plan</li>
                        </ul>
                        <div style="background: #d1fae5; padding: 0.75rem; border-radius: 6px; border-left: 3px solid #10b981; margin-top: 1rem;">
                            <strong style="color: #065f46;">✅ Development Status:</strong><br>
                            Safe for residential, commercial, and institutional use.
                        </div>
                    </div>
                '''
            }
    
    # HIGH RISK - Build detailed recommendations
    rec_summary_parts = []
    rec_html = '<div style="padding: 1rem;">'
    
    # FLOOD RECOMMENDATIONS
    if 'flood' in high_risks:
        if flood_level == 'VHS':
            rec_summary_parts.append('VERY HIGH FLOOD RISK')
            rec_html += '''
                <div style="margin-bottom: 1.5rem; padding: 1rem; background: #fee2e2; border-left: 4px solid #dc2626; border-radius: 6px;">
                    <h6 style="color: #991b1b; font-weight: 700; margin: 0 0 0.75rem 0; font-size: 1rem;">🌊 VERY HIGH FLOOD RISK</h6>
                    <div style="background: #fef2f2; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem; border: 1px solid #fca5a5;">
                        <strong style="color: #dc2626;">⚠️ DPWH/PAGASA ADVISORY:</strong><br>
                        <span style="font-size: 0.9rem;">Area is subject to severe flooding. Development is STRONGLY DISCOURAGED.</span>
                    </div>
                    
                    <p style="margin: 0 0 0.75rem 0; font-weight: 600; color: #7f1d1d;">If development must proceed (not recommended):</p>
                    <ul style="margin: 0 0 1rem 1.5rem; line-height: 1.8; font-size: 0.9rem;">
                        <li><strong>Minimum Elevation:</strong> Raise finished floor at least 2.0 meters above ground (DPWH standard for flood-prone areas)</li>
                        <li><strong>Foundation:</strong> Use elevated post/pile foundations designed by licensed engineer</li>
                        <li><strong>Materials:</strong> Use flood-resistant materials (concrete, stone) for lower floors</li>
                        <li><strong>Drainage:</strong> Install comprehensive flood control with retention basins</li>
                        <li><strong>Emergency Access:</strong> Provide elevated exits and refuge areas on upper floors</li>
                        <li><strong>Utilities:</strong> Locate electrical panels and equipment above flood level</li>
                    </ul>
                    
                    <div style="background: white; padding: 0.75rem; border-radius: 4px;">
                        <strong style="color: #dc2626;">🏛️ Required:</strong><br>
                        <span style="font-size: 0.875rem;">Consult Local DRRMO and DPWH District Office. Flood hazard disclosure required in property documents.</span>
                    </div>
                </div>
            '''
        else:  # HIGH flood
            rec_summary_parts.append('HIGH FLOOD RISK')
            rec_html += '''
                <div style="margin-bottom: 1.5rem; padding: 1rem; background: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 6px;">
                    <h6 style="color: #92400e; font-weight: 700; margin: 0 0 0.75rem 0; font-size: 1rem;">🌊 HIGH FLOOD RISK</h6>
                    <div style="background: #fffbeb; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem; border: 1px solid #fcd34d;">
                        <strong style="color: #b45309;">⚠️ DPWH/PAGASA ADVISORY:</strong><br>
                        <span style="font-size: 0.9rem;">Area is prone to flooding during heavy rainfall and typhoons.</span>
                    </div>
                    
                    <p style="margin: 0 0 0.75rem 0; font-weight: 600;">Required Flood Mitigation:</p>
                    <ul style="margin: 0 0 1rem 1.5rem; line-height: 1.8; font-size: 0.9rem;">
                        <li><strong>Floor Elevation:</strong> Raise floor at least 1.5 meters above ground (DPWH recommendation)</li>
                        <li><strong>Foundation:</strong> Use elevated foundations or flood-resistant materials</li>
                        <li><strong>Drainage:</strong> Install perimeter drains and surface water diversion</li>
                        <li><strong>Flood Barriers:</strong> Use removable barriers for doorways and openings</li>
                        <li><strong>Utilities:</strong> Elevate HVAC, water heaters, and electrical systems</li>
                        <li><strong>Grading:</strong> Slope property away from structure</li>
                    </ul>
                    
                    <div style="background: white; padding: 0.75rem; border-radius: 4px;">
                        <strong style="color: #92400e;">📋 Required:</strong><br>
                        <span style="font-size: 0.875rem;">Coordinate with Local DRRMO. Hydraulic plans must be approved by DPWH.</span>
                    </div>
                </div>
            '''
    
    # LANDSLIDE RECOMMENDATIONS
    if 'landslide' in high_risks:
        if landslide_level == 'DF':
            rec_summary_parts.append('DEBRIS FLOW ZONE')
            rec_html += '''
                <div style="margin-bottom: 1.5rem; padding: 1rem; background: #fee2e2; border-left: 4px solid #7f1d1d; border-radius: 6px;">
                    <h6 style="color: #7f1d1d; font-weight: 700; margin: 0 0 0.75rem 0; font-size: 1.1rem;">🌋 DEBRIS FLOW HAZARD ZONE</h6>
                    <div style="background: #fef2f2; padding: 1rem; border-radius: 4px; margin-bottom: 1rem; border: 2px solid #dc2626;">
                        <strong style="color: #991b1b; font-size: 1rem;">🚨 PHIVOLCS CRITICAL ADVISORY:</strong><br>
                        <p style="margin: 0.5rem 0 0 0; font-size: 0.95rem;">
                            This is a <strong>DEBRIS FLOW SUSCEPTIBILITY ZONE</strong>. Debris flows are catastrophic landslides 
                            with rocks, soil, and mud moving at high speeds. Can bury structures within minutes.
                        </p>
                    </div>
                    
                    <div style="background: #7f1d1d; color: white; padding: 1rem; border-radius: 6px; margin-bottom: 1rem;">
                        <p style="margin: 0; font-weight: 700; font-size: 1.05rem;">⛔ CONSTRUCTION PROHIBITED</p>
                        <p style="margin: 0.5rem 0 0 0; font-size: 0.9rem;">No structural mitigation can protect against debris flows. Area must remain unpopulated.</p>
                    </div>
                    
                    <p style="margin: 0 0 0.75rem 0; font-weight: 700; color: #7f1d1d;">PHIVOLCS-Mandated Actions:</p>
                    <ul style="margin: 0 0 1rem 1.5rem; line-height: 1.9; font-size: 0.9rem;">
                        <li><strong>No-Build Zone:</strong> Area designated as restricted per PHIVOLCS hazard mapping</li>
                        <li><strong>Evacuation Protocol:</strong> Mandatory evacuation during heavy rainfall (>100mm/24hrs)</li>
                        <li><strong>Early Warning:</strong> Install community rain gauges and monitoring system</li>
                        <li><strong>Land Use:</strong> Reforestation, watershed protection, or buffer zone only</li>
                        <li><strong>Relocation:</strong> If inhabited, coordinate with LGU and DSWD for relocation</li>
                    </ul>
                    
                    <div style="background: white; padding: 0.75rem; border-radius: 4px;">
                        <strong style="color: #991b1b;">📞 Mandatory:</strong><br>
                        <span style="font-size: 0.875rem;">Contact PHIVOLCS Regional Office and Local DRRMO. Secure Geohazard Assessment.</span>
                    </div>
                </div>
            '''
        elif landslide_level == 'VHS':
            rec_summary_parts.append('VERY HIGH LANDSLIDE RISK')
            rec_html += '''
                <div style="margin-bottom: 1.5rem; padding: 1rem; background: #fef3c7; border-left: 4px solid #dc2626; border-radius: 6px;">
                    <h6 style="color: #92400e; font-weight: 700; margin: 0 0 0.75rem 0; font-size: 1rem;">⛰️ VERY HIGH LANDSLIDE RISK</h6>
                    <div style="background: #fffbeb; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem; border: 1px solid #fcd34d;">
                        <strong style="color: #b45309;">⚠️ PHIVOLCS ADVISORY:</strong><br>
                        <span style="font-size: 0.9rem;">Very high landslide susceptibility. Development STRONGLY DISCOURAGED.</span>
                    </div>
                    
                    <p style="margin: 0 0 0.75rem 0; font-weight: 600;">If development cannot be avoided (extensive mitigation required):</p>
                    <ul style="margin: 0 0 1rem 1.5rem; line-height: 1.8; font-size: 0.9rem;">
                        <li><strong>Slope Stabilization:</strong> Engineered retaining walls, soil nailing, rock bolting by geotechnical engineer</li>
                        <li><strong>Subsurface Drainage:</strong> Horizontal drains or deep wells to reduce water pressure</li>
                        <li><strong>Bioengineering:</strong> Plant deep-rooted native species (bamboo, agoho trees)</li>
                        <li><strong>Slope Angle:</strong> Maintain natural slopes below 30° where possible</li>
                        <li><strong>Monitoring:</strong> Install inclinometers, rain gauges, and early warning systems</li>
                        <li><strong>Setback:</strong> Minimum 10-meter buffer from slope crest or base</li>
                    </ul>
                    
                    <div style="background: white; padding: 0.75rem; border-radius: 4px;">
                        <strong style="color: #dc2626;">🏛️ Required:</strong><br>
                        <span style="font-size: 0.875rem;">Geohazard Assessment by PHIVOLCS-accredited geologist. Clearance from Local DRRMO and Mines and Geosciences Bureau (MGB).</span>
                    </div>
                </div>
            '''
        else:  # HIGH landslide
            rec_summary_parts.append('HIGH LANDSLIDE RISK')
            rec_html += '''
                <div style="margin-bottom: 1.5rem; padding: 1rem; background: #fef9c3; border-left: 4px solid #f59e0b; border-radius: 6px;">
                    <h6 style="color: #78350f; font-weight: 700; margin: 0 0 0.75rem 0; font-size: 1rem;">⛰️ HIGH LANDSLIDE RISK</h6>
                    <div style="background: #fffbeb; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem; border: 1px solid #fde047;">
                        <strong style="color: #a16207;">⚠️ PHIVOLCS ADVISORY:</strong><br>
                        <span style="font-size: 0.9rem;">Prone to landslides during heavy rain and earthquakes. Engineering required.</span>
                    </div>
                    
                    <p style="margin: 0 0 0.75rem 0; font-weight: 600;">Required Landslide Mitigation:</p>
                    <ul style="margin: 0 0 1rem 1.5rem; line-height: 1.8; font-size: 0.9rem;">
                        <li><strong>Geotechnical Study:</strong> Site investigation with soil boring and stability analysis</li>
                        <li><strong>Retaining Walls:</strong> Gravity walls, gabions, or reinforced earth structures</li>
                        <li><strong>Surface Drainage:</strong> Lined channels to divert runoff away from slopes</li>
                        <li><strong>Terracing:</strong> Benched slopes with vegetation cover</li>
                        <li><strong>Foundation:</strong> Deep piles or piers anchored to stable bedrock</li>
                        <li><strong>Monitoring:</strong> Regular inspection for cracks, tilting, or ground movement</li>
                    </ul>
                    
                    <div style="background: white; padding: 0.75rem; border-radius: 4px;">
                        <strong style="color: #92400e;">📋 Required:</strong><br>
                        <span style="font-size: 0.875rem;">Consult geotechnical engineer. Geohazard Clearance from PHIVOLCS/MGB and Local DRRMO.</span>
                    </div>
                </div>
            '''
    
    # LIQUEFACTION RECOMMENDATIONS
    if 'liquefaction' in high_risks:
        rec_summary_parts.append('HIGH LIQUEFACTION RISK')
        rec_html += '''
            <div style="margin-bottom: 1.5rem; padding: 1rem; background: #f3e8ff; border-left: 4px solid #9333ea; border-radius: 6px;">
                <h6 style="color: #6b21a8; font-weight: 700; margin: 0 0 0.75rem 0; font-size: 1rem;">〰️ HIGH LIQUEFACTION RISK</h6>
                <div style="background: #faf5ff; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem; border: 1px solid #d8b4fe;">
                    <strong style="color: #7e22ce;">⚠️ PHIVOLCS/NBC ADVISORY:</strong><br>
                    <span style="font-size: 0.9rem;">During earthquakes, water-saturated soil may lose strength and behave like liquid, causing buildings to sink or tilt.</span>
                </div>
                
                <p style="margin: 0 0 0.75rem 0; font-weight: 600;">Required Liquefaction Mitigation (National Building Code):</p>
                <ul style="margin: 0 0 1rem 1.5rem; line-height: 1.8; font-size: 0.9rem;">
                    <li><strong>Deep Foundations:</strong> Driven piles, bored piles, or caissons through liquefiable layers to stable soil (10-20m depth)</li>
                    <li><strong>Ground Improvement:</strong> Soil densification via vibro-compaction, dynamic compaction, or stone columns</li>
                    <li><strong>Testing:</strong> Standard Penetration Test (SPT) and Cone Penetration Test (CPT) to map liquefaction zones</li>
                    <li><strong>Structural Design:</strong> Moment-resisting frames or shear walls per National Structural Code of the Philippines (NSCP)</li>
                    <li><strong>Mat Foundation:</strong> Alternative: thick reinforced concrete mat to "float" on soil</li>
                    <li><strong>Dewatering:</strong> Install gravel drains or wells to lower groundwater table</li>
                </ul>
                
                <div style="background: white; padding: 0.75rem; border-radius: 4px;">
                    <strong style="color: #6b21a8;">🏛️ Required:</strong><br>
                    <span style="font-size: 0.875rem;">Foundation design sealed by licensed Civil Engineer. Must comply with NSCP Seismic Zone 4 provisions. Coordinate with Local Building Official.</span>
                </div>
            </div>
        '''
    
    # MULTIPLE HAZARDS WARNING
    if len(high_risks) >= 2:
        rec_html += '''
            <div style="padding: 1rem; background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); border: 2px solid #dc2626; border-radius: 8px;">
                <h6 style="color: #991b1b; font-weight: 700; margin: 0 0 0.75rem 0; font-size: 1.05rem;">⚠️ MULTIPLE HAZARD EXPOSURE</h6>
                <p style="margin: 0 0 0.75rem 0; line-height: 1.7; font-size: 0.95rem; color: #7f1d1d;">
                    This location faces <strong>multiple high-severity hazards</strong>. Combined risks increase vulnerability significantly:
                </p>
                <ul style="margin: 0 0 1rem 1.5rem; line-height: 1.8; color: #7f1d1d; font-size: 0.9rem;">
                    <li>Mitigation may cost 30-50% of construction budget</li>
                    <li>Substantial long-term maintenance required</li>
                    <li>Property insurance may be unavailable or expensive</li>
                    <li>Resale value significantly reduced</li>
                </ul>
                <div style="background: #7f1d1d; color: white; padding: 0.875rem; border-radius: 6px;">
                    <strong style="font-size: 1rem;">🏛️ OFFICIAL RECOMMENDATION:</strong><br>
                    <p style="margin: 0.5rem 0 0 0; font-size: 0.9rem;">
                        <strong>Relocate to safer site.</strong> If proceeding, conduct Multi-Hazard Risk Assessment and secure clearances from PHIVOLCS, PAGASA, Local DRRMO, MGB, and DPWH.
                    </p>
                </div>
            </div>
        '''
    
    rec_html += '</div>'
    
    summary = ' + '.join(rec_summary_parts) if rec_summary_parts else 'Low Risk'
    
    return {
        'summary': summary,
        'details': rec_html
    }

@api_view(['GET'])
def get_datasets(request):
    """Get list of uploaded datasets"""
    try:
        datasets = HazardDataset.objects.all().values(
            'id', 'name', 'dataset_type', 'upload_date', 'file_name'
        )
        return Response(list(datasets))
    
    except Exception as e:
        return Response({'error': str(e)}, status=500)
    
@api_view(['GET'])
def get_nearby_facilities(request):
    """Get facilities within specified radius with disaster-priority grouping"""
    try:
        lat = float(request.GET.get('lat'))
        lng = float(request.GET.get('lng'))
        radius = int(request.GET.get('radius', 3000))
        
        facilities = OverpassClient.query_facilities(lat, lng, radius)
        
        # Calculate distances
        for facility in facilities:
            distance = calculate_distance(lat, lng, facility['lat'], facility['lng'])
            facility['distance_meters'] = distance
            facility['distance_km'] = round(distance / 1000, 2)
            facility['distance_display'] = format_distance(distance)
            
            # Add walkability flag (critical for disasters)
            facility['is_walkable'] = distance <= 500  # Within 500m
        
        facilities.sort(key=lambda x: x['distance_meters'])
        
        # Reorganize by disaster priority
        evacuation_centers = []
        medical = []
        emergency_services = []
        essential_services = []
        other_facilities = []
        
        for f in facilities:
            ftype = f['facility_type']
            
            # Priority 1: Evacuation (schools, gyms, community centers as shelters)
            if ftype in ['school', 'community_centre', 'kindergarten', 'college', 'university']:
                f['subcategory'] = 'evacuation'
                f['priority'] = 1
                evacuation_centers.append(f)
            
            # Priority 2: Medical
            elif ftype in ['hospital', 'clinic', 'doctors', 'pharmacy']:
                f['subcategory'] = 'medical'
                f['priority'] = 2
                medical.append(f)
            
            # Priority 3: Emergency Services
            elif ftype in ['fire_station', 'police']:
                f['subcategory'] = 'emergency_services'
                f['priority'] = 3
                emergency_services.append(f)
            
            # Priority 4: Essential Services (food, water)
            elif ftype in ['marketplace', 'supermarket', 'convenience']:
                f['subcategory'] = 'essential'
                f['priority'] = 4
                essential_services.append(f)
            
            # Priority 5: Everything else
            else:
                f['subcategory'] = 'other'
                f['priority'] = 5
                other_facilities.append(f)
        
        # Find nearest of each critical type
        nearest_evacuation = evacuation_centers[0] if evacuation_centers else None
        nearest_hospital = next((f for f in medical if f['facility_type'] in ['hospital', 'clinic']), None)
        nearest_fire = next((f for f in emergency_services if f['facility_type'] == 'fire_station'), None)
        
        result = {
            'summary': {
                'nearest_evacuation': {
                    'name': nearest_evacuation['name'] if nearest_evacuation else 'None within 3km',
                    'distance': nearest_evacuation['distance_display'] if nearest_evacuation else 'N/A',
                    'is_walkable': nearest_evacuation['is_walkable'] if nearest_evacuation else False,
                } if nearest_evacuation else None,
                'nearest_hospital': {
                    'name': nearest_hospital['name'] if nearest_hospital else 'None within 3km',
                    'distance': nearest_hospital['distance_display'] if nearest_hospital else 'N/A',
                    'is_walkable': nearest_hospital['is_walkable'] if nearest_hospital else False,
                } if nearest_hospital else None,
                'nearest_fire_station': {
                    'name': nearest_fire['name'] if nearest_fire else 'None within 3km',
                    'distance': nearest_fire['distance_display'] if nearest_fire else 'N/A',
                    'is_walkable': nearest_fire['is_walkable'] if nearest_fire else False,
                } if nearest_fire else None,
            },
            'evacuation_centers': evacuation_centers[:10],
            'medical': medical[:10],
            'emergency_services': emergency_services[:10],
            'essential_services': essential_services[:10],
            'other': other_facilities[:10],
            'counts': {
                'evacuation': len(evacuation_centers),
                'medical': len(medical),
                'emergency_services': len(emergency_services),
                'essential': len(essential_services),
                'other': len(other_facilities),
                'total': len(facilities)
            }
        }
        
        return Response(result)
        
    except ValueError:
        return Response({'error': 'Invalid coordinates or radius'}, status=400)
    except Exception as e:
        print(f"Error in get_nearby_facilities: {e}")
        return Response({'error': str(e)}, status=500)


def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two points using Haversine formula
    Returns distance in meters
    """
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    
    # Radius of earth in meters
    r = 6371000
    
    return c * r


def format_distance(meters):
    """Format distance for display"""
    if meters < 1000:
        return f"{int(meters)} m"
    else:
        km = meters / 1000
        return f"{km:.1f} km"

@api_view(['GET'])
def get_location_info(request):
    """Get administrative boundary info for a location"""
    try:
        lat = float(request.GET.get('lat'))
        lng = float(request.GET.get('lng'))
        
        location_info = OverpassClient.get_location_info(lat, lng)
        
        return Response(location_info)
        
    except ValueError:
        return Response({'error': 'Invalid coordinates'}, status=400)
    except Exception as e:
        return Response({'error': str(e)}, status=500)