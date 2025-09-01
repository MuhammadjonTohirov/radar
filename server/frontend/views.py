from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.conf import settings
from radars.models import Radar
from .forms import RadarForm
import json


def login_view(request):
    if request.user.is_authenticated:
        return redirect('frontend:radar_list')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('frontend:radar_list')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = AuthenticationForm()
    
    return render(request, 'frontend/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('frontend:login')


@login_required
def radar_list(request):
    # Get all active radars
    radars = Radar.objects.filter(active=True).select_related('created_by', 'verified_by')
    
    # Search functionality
    search = request.GET.get('search')
    if search:
        radars = radars.filter(
            Q(notes__icontains=search) | 
            Q(id__icontains=search)
        )
    
    # Filter by type
    radar_type = request.GET.get('type')
    if radar_type:
        radars = radars.filter(type=radar_type)
    
    # Filter by verification status
    verified = request.GET.get('verified')
    if verified == 'true':
        radars = radars.filter(verified=True)
    elif verified == 'false':
        radars = radars.filter(verified=False)
    
    # Order by creation date (newest first)
    radars = radars.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(radars, 25)  # Show 25 radars per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'radars': page_obj,
        'radar_types': Radar.TYPE_CHOICES,
    }
    
    return render(request, 'frontend/radar_list.html', context)


@login_required
def radar_add(request):
    if request.method == 'POST':
        form = RadarForm(request.POST)
        if form.is_valid():
            radar = form.save(commit=False)
            radar.created_by = request.user
            radar.save()
            messages.success(request, 'Radar added successfully!')
            return redirect('frontend:radar_list')
    else:
        form = RadarForm()
    
    context = {
        'form': form,
        'radar': None,
        'settings': settings,
    }
    
    return render(request, 'frontend/radar_form.html', context)


@login_required
def radar_edit(request, radar_id):
    radar = get_object_or_404(Radar, id=radar_id, active=True)
    
    if request.method == 'POST':
        form = RadarForm(request.POST, instance=radar)
        if form.is_valid():
            form.save()
            messages.success(request, 'Radar updated successfully!')
            return redirect('frontend:radar_list')
    else:
        form = RadarForm(instance=radar)
    
    context = {
        'form': form,
        'radar': radar,
        'settings': settings,
    }
    
    return render(request, 'frontend/radar_form.html', context)


@login_required
def radar_delete(request, radar_id):
    radar = get_object_or_404(Radar, id=radar_id, active=True)
    
    if request.method == 'POST':
        radar.active = False  # Soft delete
        radar.save()
        messages.success(request, 'Radar deleted successfully!')
        return redirect('frontend:radar_list')
    
    return render(request, 'frontend/radar_confirm_delete.html', {'radar': radar})
