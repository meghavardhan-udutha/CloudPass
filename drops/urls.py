from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('access/', views.access_page, name='access_page'),
    path('access/<str:code>/', views.access_page, name='access_page_code'),
    path('upload/', views.upload, name='upload'),
    path('api/access/<str:code>/', views.access, name='access'),
    path('api/access/<str:code>/download/<int:file_id>/', views.download_file, name='download_file'),
    path('download/<str:code>/', views.download_zip, name='download_zip'),
]
