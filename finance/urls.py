from django.urls import path
from . import views

urlpatterns = [
    # Payment URLs
    path('payment/', views.payement_detail, name='payement_detail'),
    path('process-payment/', views.process_payment, name='process_payment'),
    # M-Pesa URLs
    path('mpesa/pay/', views.mpesa_payment, name='mpesa_payment'),
    path('mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
]