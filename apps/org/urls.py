"""مسیرهای ساختار سازمانی و قراردادها."""
from django.urls import path

from . import views

app_name = "org"

urlpatterns = [
    path("departments/", views.DepartmentListView.as_view(), name="department_list"),
    path("departments/add/", views.DepartmentCreateView.as_view(), name="department_create"),
    path("departments/<int:pk>/edit/", views.DepartmentUpdateView.as_view(), name="department_update"),
    path("locations/", views.LocationListView.as_view(), name="location_list"),
    path("locations/add/", views.LocationCreateView.as_view(), name="location_create"),
    path("locations/<int:pk>/edit/", views.LocationUpdateView.as_view(), name="location_update"),
    path("contractors/", views.ContractorListView.as_view(), name="contractor_list"),
    path("contractors/add/", views.ContractorCreateView.as_view(), name="contractor_create"),
    path("contractors/<int:pk>/", views.ContractorDetailView.as_view(), name="contractor_detail"),
    path("contractors/<int:pk>/edit/", views.ContractorUpdateView.as_view(), name="contractor_update"),
    path("contracts/", views.ContractListView.as_view(), name="contract_list"),
    path("contracts/add/", views.ContractCreateView.as_view(), name="contract_create"),
    path("contracts/<int:pk>/", views.ContractDetailView.as_view(), name="contract_detail"),
    path("contracts/<int:pk>/edit/", views.ContractUpdateView.as_view(), name="contract_update"),
    path("contracts/<int:pk>/generate-visits/", views.contract_generate_visits, name="contract_generate_visits"),
]
