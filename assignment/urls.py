"""
URL configuration for assignment project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from accounts.views.signUpview import SignUpView
from accounts.views.login_view import CustomTokenObtainPairView
from rest_framework.routers import DefaultRouter
from tests.views.test_viewset import TestViewSet
from courses.views.course_viewset import CourseViewSet
from payments.views.post_viewset import PaymentViewSet
from payments.views.get_viewset import MePaymentsViewSet
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

router = DefaultRouter(trailing_slash=False)
router.register(r'tests', TestViewSet, basename='test')
router.register(r'courses', CourseViewSet, basename='course')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'me/payments', MePaymentsViewSet, basename='me_payment')



urlpatterns = [
    path('admin/', admin.site.urls),
    path('signup', SignUpView.as_view()),
    path('login', CustomTokenObtainPairView.as_view()),
    path('', include(router.urls)),
    
    # OpenAPI 스키마 및 문서
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
