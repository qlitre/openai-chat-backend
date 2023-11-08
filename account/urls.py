from django.urls import path
from account.views import GetCSRFToken, CheckAuthenticatedView

urlpatterns = [
    path('csrf_cookie/', GetCSRFToken.as_view(), name='csrf_cookie'),
    path('checkauth/', CheckAuthenticatedView.as_view(), name='check_auth'),
]
