from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from .models import HazardDataset, FloodSusceptibility, LandslideSusceptibility, LiquefactionSusceptibility, BarangayBoundaryNew

@admin.register(HazardDataset)
class HazardDatasetAdmin(admin.ModelAdmin):
    list_display = ['name', 'dataset_type', 'upload_date', 'file_name']
    list_filter = ['dataset_type', 'upload_date']
    search_fields = ['name', 'file_name']
    readonly_fields = ['upload_date']

@admin.register(FloodSusceptibility)
class FloodSusceptibilityAdmin(GISModelAdmin):
    list_display = ['flood_susc', 'original_code', 'dataset', 'orig_fid']
    list_filter = ['flood_susc', 'dataset']
    search_fields = ['orig_fid']

@admin.register(LandslideSusceptibility) 
class LandslideSusceptibilityAdmin(GISModelAdmin):
    list_display = ['landslide_susc', 'original_code', 'dataset', 'orig_fid']
    list_filter = ['landslide_susc', 'dataset']
    search_fields = ['orig_fid']

@admin.register(LiquefactionSusceptibility)
class LiquefactionSusceptibilityAdmin(GISModelAdmin):
    list_display = ['liquefaction_susc', 'original_code', 'dataset']
    list_filter = ['liquefaction_susc', 'dataset']

from .models import Facility

@admin.register(Facility)
class FacilityAdmin(GISModelAdmin):
    list_display = ['name', 'facility_type', 'category', 'osm_id']
    list_filter = ['category', 'facility_type']
    search_fields = ['name']


@admin.register(BarangayBoundaryNew)
class BarangayBoundaryNewAdmin(GISModelAdmin):
    list_display = ['adm4_en', 'adm3_en', 'adm2_en', 'area_sqkm', 'dataset']
    list_filter = ['adm3_en', 'adm2_en', 'dataset']
    search_fields = ['adm4_en', 'adm3_en', 'adm4_pcode']
    
    fieldsets = (
        ('Barangay Information', {
            'fields': ('adm4_en', 'adm4_pcode', 'area_sqkm')
        }),
        ('Administrative Hierarchy', {
            'fields': ('adm3_en', 'adm3_pcode', 'adm2_en', 'adm2_pcode', 'adm1_en', 'adm1_pcode')
        }),
        ('Metadata', {
            'fields': ('dataset', 'date', 'valid_on', 'valid_to', 'objectid')
        }),
        ('Geometry', {
            'fields': ('geometry', 'shape_length', 'shape_area')
        }),
    )