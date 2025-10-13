# casos/templatetags/file_icons.py

from django import template
from django.utils import timezone
from django.urls import resolve, reverse
from django.http import HttpRequest

register = template.Library()

@register.filter
def get_file_icon(filename):
    """
    Recebe um nome de arquivo e retorna a classe CSS do Font Awesome
    correspondente à sua extensão.
    """
    # Converte para minúsculas para a comparação não falhar
    filename_lower = filename.lower()

    if filename_lower.endswith(('.pdf')):
        return 'fa-solid fa-file-pdf'
    
    if filename_lower.endswith(('.doc', '.docx')):
        return 'fa-solid fa-file-word'
        
    if filename_lower.endswith(('.xls', '.xlsx')):
        return 'fa-solid fa-file-excel'
        
    if filename_lower.endswith(('.ppt', '.pptx')):
        return 'fa-solid fa-file-powerpoint'

    if filename_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg')):
        return 'fa-solid fa-file-image'
        
    if filename_lower.endswith(('.zip', '.rar', '.7z')):
        return 'fa-solid fa-file-zipper'
        
    if filename_lower.endswith(('.mp4', '.mov', '.avi')):
        return 'fa-solid fa-file-video'
        
    if filename_lower.endswith(('.mp3', '.wav', '.ogg')):
        return 'fa-solid fa-file-audio'

    # Se não corresponder a nenhum dos acima, retorna um ícone genérico de arquivo
    return 'fa-solid fa-file'

@register.filter
def tempo_decorrido(data_entrada):
    """
    Calcula e formata o tempo decorrido desde uma data de entrada.
    """
    if not data_entrada:
        return ""
    
    agora = timezone.now()
    diferenca = agora - data_entrada
    
    dias = diferenca.days
    
    if dias > 1:
        return f"há {dias} dias"
    elif dias == 1:
        return "há 1 dia"
    else:
        # Se for menos de um dia, calculamos as horas
        horas = diferenca.seconds // 3600
        if horas > 1:
            return f"há {horas} horas"
        elif horas == 1:
            return "há 1 hora"
        else:
            minutos = diferenca.seconds // 60
            return f"há {minutos} minutos"
        
@register.filter
def format_timedelta(timedelta_obj):
    """
    Converte um objeto timedelta em uma string no formato HHH:MM:SS.
    Ex: 25:30:00
    """
    if not timedelta_obj:
        return "00:00:00"
    
    # total_seconds() nos dá o total de segundos na duração
    total_seconds = int(timedelta_obj.total_seconds())
    
    # Faz a matemática para converter segundos em horas, minutos e segundos restantes
    horas = total_seconds // 3600
    minutos = (total_seconds % 3600) // 60
    segundos = total_seconds % 60
    
    # zfill(2) garante que minutos e segundos sempre tenham 2 dígitos (ex: 05)
    return f"{horas}:{str(minutos).zfill(2)}:{str(segundos).zfill(2)}"

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.simple_tag(takes_context=True)
def call_view(context, view_name, *args, **kwargs):
    """
    Permite chamar uma view de dentro de um template.
    """
    request = context['request']
    
    # Copia os parâmetros GET da requisição original
    request_get = request.GET.copy()
    
    # Adiciona/sobrescreve com os kwargs passados
    for key, value in kwargs.items():
        request_get[key] = value

    # Encontra a view e a chama
    view, _, _ = resolve(reverse(view_name))
    
    # Cria um request "fake" para a view
    fake_request = HttpRequest()
    fake_request.method = 'GET'
    fake_request.GET = request_get
    fake_request.user = request.user

    # Chama a view e retorna sua resposta (o HTML renderizado)
    return view(fake_request)

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)