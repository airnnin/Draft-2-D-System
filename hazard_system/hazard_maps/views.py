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
        
        return Response({
            'flood': {
                'level': flood_result.flood_susc if flood_result else None,
                'label': flood_result.get_flood_susc_display() if flood_result else 'No Data Available'
            },
            'landslide': {
                'level': landslide_result.landslide_susc if landslide_result else None,
                'label': landslide_result.get_landslide_susc_display() if landslide_result else 'No Data Available'
            },
            'liquefaction': {
                'level': liquefaction_result.liquefaction_susc if liquefaction_result else None,
                'label': liquefaction_result.get_liquefaction_susc_display() if liquefaction_result else 'No Data Available'
            }
        })
        
    except ValueError:
        return Response({'error': 'Invalid coordinates'}, status=400)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

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
    """Get facilities within specified radius using Overpass API"""
    try:
        lat = float(request.GET.get('lat'))
        lng = float(request.GET.get('lng'))
        radius = int(request.GET.get('radius', 3000))  # Default 3km in meters
        
        # Query Overpass API
        facilities = OverpassClient.query_facilities(lat, lng, radius)
        
        # Calculate distances and sort
        for facility in facilities:
            distance = calculate_distance(
                lat, lng,
                facility['lat'], facility['lng']
            )
            facility['distance_meters'] = distance
            facility['distance_km'] = round(distance / 1000, 2)
            facility['distance_display'] = format_distance(distance)
        
        # Sort by distance
        facilities.sort(key=lambda x: x['distance_meters'])
        
        # Group by category
        result = {
            'emergency': [f for f in facilities if f['category'] == 'emergency'],
            'everyday': [f for f in facilities if f['category'] == 'everyday'],
            'government': [f for f in facilities if f['category'] == 'government'],
        }
        
        # Add counts
        result['counts'] = {
            'emergency': len(result['emergency']),
            'everyday': len(result['everyday']),
            'government': len(result['government']),
            'total': len(facilities)
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