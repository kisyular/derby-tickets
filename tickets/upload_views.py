from django.shortcuts import render, redirect
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.conf import settings
import pandas as pd
import json
import os
import tempfile
import csv
from io import StringIO
from tickets.models import Category, Ticket
from django.contrib.auth.models import User


def is_admin(user):
    """Check if user is admin/staff"""
    return user.is_authenticated and (user.is_staff or user.is_superuser)


@user_passes_test(is_admin)
def data_upload_dashboard(request):
    """Main data upload dashboard"""
    context = {
        'total_tickets': Ticket.objects.count(),
        'total_categories': Category.objects.count(),
        'total_users': User.objects.count(),
    }
    return render(request, 'tickets/admin/data_upload_dashboard.html', context)


@user_passes_test(is_admin)
def upload_tickets(request):
    """Tickets upload page"""
    return render(request, 'tickets/admin/upload_tickets.html')


@user_passes_test(is_admin)
def upload_categories(request):
    """Categories upload page"""
    existing_categories = Category.objects.all().order_by('name')
    context = {
        'existing_categories': existing_categories
    }
    return render(request, 'tickets/admin/upload_categories.html', context)


@user_passes_test(is_admin)
@require_http_methods(["POST"])
def validate_csv(request):
    """Validate uploaded CSV file and return preview"""
    try:
        file_type = request.POST.get('file_type')  # 'tickets' or 'categories'
        csv_file = request.FILES.get('csv_file')
        
        if not csv_file:
            return JsonResponse({'error': 'No file uploaded'}, status=400)
        
        # Read CSV content
        csv_content = csv_file.read().decode('utf-8')
        df = pd.read_csv(StringIO(csv_content))
        
        if file_type == 'tickets':
            validation_result = validate_tickets_csv(df)
        elif file_type == 'categories':
            validation_result = validate_categories_csv(df)
        else:
            return JsonResponse({'error': 'Invalid file type'}, status=400)
        
        # Save temporary file for later processing
        temp_filename = f"{file_type}_{request.user.id}_{csv_file.name}"
        temp_path = default_storage.save(f"temp_uploads/{temp_filename}", ContentFile(csv_content.encode('utf-8')))
        
        validation_result['temp_file_path'] = temp_path
        validation_result['total_rows'] = len(df)
        
        return JsonResponse(validation_result)
        
    except Exception as e:
        return JsonResponse({'error': f'Error processing file: {str(e)}'}, status=400)


def validate_tickets_csv(df):
    """Validate tickets CSV format and content"""
    required_columns = ['Subject', 'Description', 'Priority', 'Status', 'Category']
    optional_columns = ['Created By', 'Assigned To', 'Created At', 'Closed At', 'Department', 'Location']
    
    # Check required columns
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        return {
            'valid': False,
            'error': f'Missing required columns: {", ".join(missing_columns)}',
            'required_columns': required_columns,
            'optional_columns': optional_columns
        }
    
    # Validate data content
    issues = []
    preview_data = []
    
    # Check for empty required fields
    for idx, row in df.head(10).iterrows():  # Preview first 10 rows
        row_issues = []
        
        if pd.isna(row.get('Subject')) or not str(row.get('Subject')).strip():
            row_issues.append('Missing Subject')
        
        priority = row.get('Priority')
        if priority and priority not in ['Low', 'Medium', 'High', 'Urgent']:
            row_issues.append(f'Invalid Priority: {priority}')
        
        status = row.get('Status')
        if status and status not in ['Open', 'In Progress', 'Resolved', 'Closed']:
            row_issues.append(f'Invalid Status: {status}')
        
        preview_data.append({
            'row_number': idx + 1,
            'subject': str(row.get('Subject', ''))[:50],
            'priority': str(row.get('Priority', '')),
            'status': str(row.get('Status', '')),
            'category': str(row.get('Category', '')),
            'issues': row_issues
        })
        
        if row_issues:
            issues.extend([f"Row {idx + 1}: {issue}" for issue in row_issues])
    
    return {
        'valid': len(issues) == 0,
        'issues': issues[:10],  # Limit to first 10 issues
        'preview_data': preview_data,
        'required_columns': required_columns,
        'optional_columns': optional_columns,
        'total_issues': len(issues)
    }


def validate_categories_csv(df):
    """Validate categories CSV format and content"""
    required_columns = ['name']
    optional_columns = ['description']
    
    # Check required columns (case insensitive)
    df_columns_lower = [col.lower() for col in df.columns]
    missing_columns = [col for col in required_columns if col.lower() not in df_columns_lower]
    
    if missing_columns:
        return {
            'valid': False,
            'error': f'Missing required columns: {", ".join(missing_columns)}',
            'required_columns': required_columns,
            'optional_columns': optional_columns
        }
    
    # Find the actual column name for 'name'
    name_column = None
    for col in df.columns:
        if col.lower() == 'name':
            name_column = col
            break
    
    issues = []
    preview_data = []
    existing_categories = set(Category.objects.values_list('name', flat=True))
    
    # Check for empty names and duplicates
    for idx, row in df.head(10).iterrows():  # Preview first 10 rows
        row_issues = []
        category_name = str(row.get(name_column, '')).strip()
        
        if not category_name or category_name == 'nan':
            row_issues.append('Missing category name')
        elif category_name in existing_categories:
            row_issues.append('Category already exists')
        
        preview_data.append({
            'row_number': idx + 1,
            'name': category_name,
            'description': str(row.get('description', ''))[:100] if 'description' in df.columns else '',
            'issues': row_issues
        })
        
        if row_issues:
            issues.extend([f"Row {idx + 1}: {issue}" for issue in row_issues])
    
    return {
        'valid': len(issues) == 0,
        'issues': issues[:10],
        'preview_data': preview_data,
        'required_columns': required_columns,
        'optional_columns': optional_columns,
        'total_issues': len(issues)
    }


@user_passes_test(is_admin)
@require_http_methods(["POST"])
def process_upload(request):
    """Process various upload actions"""
    try:
        action = request.POST.get('action')
        
        if action == 'list_categories':
            return handle_list_categories(request)
        elif action == 'category_stats':
            return handle_category_stats(request)
        elif action == 'add_single':
            return handle_add_single_category(request)
        elif action == 'upload_categories':
            return handle_upload_categories(request)
        elif action == 'validate':
            return handle_validate_csv(request)
        elif action == 'import':
            return handle_import_csv(request)
        else:
            return JsonResponse({'error': 'Invalid action'}, status=400)
            
    except Exception as e:
        return JsonResponse({'error': f'Error processing request: {str(e)}'}, status=500)


def handle_list_categories(request):
    """Handle listing current categories"""
    try:
        categories = Category.objects.all().order_by('name')
        category_list = []
        
        for category in categories:
            category_list.append({
                'name': category.name,
                'description': getattr(category, 'description', ''),
                'ticket_count': category.ticket_set.count()
            })
        
        return JsonResponse({
            'success': True,
            'categories': category_list
        })
    except Exception as e:
        return JsonResponse({'error': f'Error loading categories: {str(e)}'}, status=500)


def handle_category_stats(request):
    """Handle category statistics"""
    try:
        return JsonResponse({
            'success': True,
            'total_categories': Category.objects.count(),
            'total_tickets': Ticket.objects.count(),
            'tickets_with_categories': Ticket.objects.filter(category__isnull=False).count(),
            'tickets_without_categories': Ticket.objects.filter(category__isnull=True).count()
        })
    except Exception as e:
        return JsonResponse({'error': f'Error getting stats: {str(e)}'}, status=500)


def handle_add_single_category(request):
    """Handle adding a single category"""
    try:
        category_name = request.POST.get('category_name', '').strip()
        description = request.POST.get('description', '').strip()
        
        if not category_name:
            return JsonResponse({'error': 'Category name is required'}, status=400)
        
        if Category.objects.filter(name=category_name).exists():
            return JsonResponse({'error': 'Category already exists'}, status=400)
        
        category = Category.objects.create(name=category_name, description=description)
        
        return JsonResponse({
            'success': True,
            'message': f'Category "{category_name}" created successfully',
            'category': {
                'id': category.id,
                'name': category.name,
                'description': description
            }
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error creating category: {str(e)}'}, status=500)


def handle_upload_categories(request):
    """Handle category uploads"""
    try:
        upload_type = request.POST.get('upload_type')
        
        if upload_type == 'predefined':
            # Load predefined categories using management command
            call_command('load_categories', verbosity=0)
            
            return JsonResponse({
                'success': True,
                'message': 'Predefined categories loaded successfully',
                'stats': {
                    'created': 7,  # Standard IT categories
                    'duplicates': 0,
                    'errors': 0,
                    'total': 7
                }
            })
            
        elif upload_type == 'csv':
            csv_file = request.FILES.get('csv_file')
            if not csv_file:
                return JsonResponse({'error': 'No CSV file provided'}, status=400)
            
            clean_categories = request.POST.get('clean_categories') == 'true'
            skip_duplicates = request.POST.get('skip_duplicates') == 'true'
            
            # Process CSV file
            result = process_categories_csv_upload(csv_file, clean_categories, skip_duplicates)
            return JsonResponse(result)
            
        else:
            return JsonResponse({'error': 'Invalid upload type'}, status=400)
            
    except Exception as e:
        return JsonResponse({'error': f'Error uploading categories: {str(e)}'}, status=500)


def handle_validate_csv(request):
    """Handle CSV validation"""
    try:
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            return JsonResponse({'error': 'No file uploaded'}, status=400)
        
        # Read and validate CSV
        csv_content = csv_file.read().decode('utf-8')
        df = pd.read_csv(StringIO(csv_content))
        
        # Perform validation
        validation_result = validate_tickets_csv(df)
        
        if validation_result.get('valid', False):
            # Save temporary file for later processing
            temp_filename = f"tickets_{request.user.id}_{csv_file.name}"
            temp_path = default_storage.save(f"temp_uploads/{temp_filename}", ContentFile(csv_content.encode('utf-8')))
            validation_result['temp_file_path'] = temp_path
        
        return JsonResponse(validation_result)
        
    except Exception as e:
        return JsonResponse({'error': f'Error validating file: {str(e)}'}, status=400)


def handle_import_csv(request):
    """Handle CSV import"""
    try:
        csv_file = request.FILES.get('csv_file')
        config = json.loads(request.POST.get('config', '{}'))
        
        if not csv_file:
            return JsonResponse({'error': 'No file uploaded'}, status=400)
        
        # Save temporary file
        temp_filename = f"import_tickets_{request.user.id}_{csv_file.name}"
        temp_path = default_storage.save(f"temp_uploads/{temp_filename}", ContentFile(csv_file.read()))
        actual_path = default_storage.path(temp_path)
        
        # Use management command to process
        if config.get('clean_before_import', False):
            call_command('load_tickets', actual_path, '--clean', verbosity=0)
        else:
            call_command('load_tickets', actual_path, verbosity=0)
        
        # Clean up temporary file
        default_storage.delete(temp_path)
        
        return JsonResponse({
            'success': True,
            'message': 'Tickets imported successfully',
            'stats': {
                'processed': 'Unknown',  # Could be enhanced with actual stats
                'created': 'Unknown',
                'updated': 'Unknown',
                'failed': 0
            }
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error importing tickets: {str(e)}'}, status=500)


def process_categories_csv_upload(csv_file, clean_existing=False, skip_duplicates=True):
    """Process uploaded categories CSV"""
    try:
        # Read CSV
        csv_content = csv_file.read().decode('utf-8')
        df = pd.read_csv(StringIO(csv_content))
        
        if clean_existing:
            Category.objects.all().delete()
        
        created_count = 0
        duplicate_count = 0
        error_count = 0
        
        for _, row in df.iterrows():
            try:
                category_name = str(row.get('category_name', row.get('name', ''))).strip()
                description = str(row.get('description', '')).strip()
                
                if not category_name:
                    error_count += 1
                    continue
                
                if Category.objects.filter(name=category_name).exists():
                    if skip_duplicates:
                        duplicate_count += 1
                        continue
                    else:
                        # Update existing
                        Category.objects.filter(name=category_name).update(description=description)
                        continue
                
                Category.objects.create(name=category_name, description=description)
                created_count += 1
                
            except Exception:
                error_count += 1
        
        return {
            'success': True,
            'message': f'Categories processed: {created_count} created, {duplicate_count} duplicates, {error_count} errors',
            'stats': {
                'created': created_count,
                'duplicates': duplicate_count,
                'errors': error_count,
                'total': len(df)
            }
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f'Error processing CSV: {str(e)}',
            'stats': {
                'created': 0,
                'duplicates': 0,
                'errors': 1,
                'total': 0
            }
        }
        
    except Exception as e:
        return JsonResponse({'error': f'Error processing upload: {str(e)}'}, status=500)


def process_categories_csv(file_path, clean_existing=False):
    """Process categories CSV file"""
    try:
        df = pd.read_csv(file_path)
        
        # Find the name column (case insensitive)
        name_column = None
        for col in df.columns:
            if col.lower() == 'name':
                name_column = col
                break
        
        if clean_existing:
            Category.objects.all().delete()
        
        created_count = 0
        skipped_count = 0
        
        for _, row in df.iterrows():
            category_name = str(row.get(name_column, '')).strip()
            description = str(row.get('description', '')) if 'description' in df.columns else ''
            
            if not category_name or category_name == 'nan':
                continue
            
            # Check if category already exists
            if Category.objects.filter(name=category_name).exists():
                skipped_count += 1
                continue
            
            # Create category
            Category.objects.create(
                name=category_name,
                description=description if description != 'nan' else ''
            )
            created_count += 1
        
        return {
            'success': True,
            'message': f'Categories processed: {created_count} created, {skipped_count} skipped'
        }
        
    except Exception as e:
        return {'success': False, 'message': f'Error: {str(e)}'}


@user_passes_test(is_admin)
def download_sample_csv(request, sample_type):
    """Download sample CSV files"""
    if sample_type == 'tickets':
        return download_tickets_sample()
    elif sample_type == 'categories':
        return download_categories_sample()
    else:
        return HttpResponse('Invalid file type', status=400)


def download_tickets_sample():
    """Generate and download sample tickets CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sample_tickets.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Subject', 'Description', 'Priority', 'Status', 'Category',
        'Created By', 'Assigned To', 'Created At', 'Department', 'Location'
    ])
    writer.writerow([
        'Sample Ticket 1', 'This is a sample ticket description', 'High', 'Open', 'Hardware',
        'john.doe@company.com', 'admin@company.com', '11/3/2024 1:37 pm UTC', 'IT', 'Main Office'
    ])
    writer.writerow([
        'Network Issue', 'Unable to connect to company network', 'Medium', 'In Progress', 'Network',
        'jane.smith@company.com', '', '11/3/2024 2:00 pm UTC', 'Operations', 'Branch Office'
    ])
    
    return response


def download_categories_sample():
    """Generate and download sample categories CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sample_categories.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['name', 'description'])
    writer.writerow(['Hardware', 'Hardware related issues and requests'])
    writer.writerow(['Software', 'Software installation and troubleshooting'])
    writer.writerow(['Network', 'Network connectivity and infrastructure'])
    
    return response


@user_passes_test(is_admin)
@require_http_methods(["POST"])
def add_category_manual(request):
    """Add a single category manually"""
    try:
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        
        if not name:
            return JsonResponse({'error': 'Category name is required'}, status=400)
        
        if Category.objects.filter(name=name).exists():
            return JsonResponse({'error': 'Category already exists'}, status=400)
        
        category = Category.objects.create(name=name, description=description)
        
        return JsonResponse({
            'success': True,
            'message': f'Category "{name}" created successfully',
            'category': {
                'id': category.id,
                'name': category.name,
                'description': category.description
            }
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error creating category: {str(e)}'}, status=500)


@user_passes_test(is_admin)
def scan_database(request):
    """Database scanning view - displays current database contents"""
    context = {
        'total_tickets': Ticket.objects.count(),
        'total_categories': Category.objects.count(),
        'total_users': User.objects.count(),
        'recent_tickets': Ticket.objects.select_related('created_by', 'category').order_by('-created_at')[:10],
        'categories': Category.objects.all().order_by('name'),
        'recent_users': User.objects.order_by('-date_joined')[:10],
    }
    
    if request.headers.get('Accept') == 'application/json':
        # Return JSON for AJAX requests
        return JsonResponse({
            'success': True,
            'stats': {
                'total_tickets': context['total_tickets'],
                'total_categories': context['total_categories'],
                'total_users': context['total_users'],
            },
            'recent_tickets': [
                {
                    'id': ticket.ticket_number or ticket.id,
                    'title': ticket.title,
                    'user': ticket.created_by.email,
                    'category': ticket.category.name if ticket.category else 'None',
                    'status': ticket.status,
                    'created_at': ticket.created_at.strftime('%Y-%m-%d %H:%M:%S')
                }
                for ticket in context['recent_tickets']
            ],
            'categories': [
                {
                    'name': cat.name,
                    'description': getattr(cat, 'description', ''),
                    'ticket_count': cat.ticket_set.count()
                }
                for cat in context['categories']
            ]
        })
    
    return render(request, 'tickets/admin/scan_database.html', context)
