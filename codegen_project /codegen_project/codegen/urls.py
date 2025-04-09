from django.urls import path
from .views import generate_code, index, fetch_history, continue_project, index,delete_project, install_dependencies, generate_module

urlpatterns = [
    path("", index, name="index"),
    path("generate_code/", generate_code, name="generate_code"),
    path("history/", fetch_history, name="fetch_history"),
    path("continue_project/", continue_project, name="continue_project"),
    path('delete_project/',delete_project, name='delete_project'),
    path('install_dependencies/',install_dependencies,name='install_dependencies'),
    path("generate_module/", generate_module, name="generate_module"),
    


]