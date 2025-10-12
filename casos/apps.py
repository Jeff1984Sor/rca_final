from django.apps import AppConfig


class CasosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'casos'

   # def ready(self):
        # Importa os sinais para que eles sejam registrados quando o app iniciar
       # import casos.signals
