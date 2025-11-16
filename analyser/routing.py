# analyser/routing.py

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Esta URL será como 'ws://localhost:8000/ws/analise/123/'
    re_path(r'ws/analise/(?P<resultado_id>\d+)/$', consumers.AnalysisConsumer.as_asgi()),
]