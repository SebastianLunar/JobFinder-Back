from django.urls import path
from . import views

urlpatterns = [
    path('jobs/', views.scrape_linkedin, name='get_jobs'),
]
