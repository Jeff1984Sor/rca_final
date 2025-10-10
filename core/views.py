from django.shortcuts import render

def home(request):
    # Por enquanto, a view só precisa renderizar o template.
    # No futuro, podemos adicionar aqui um painel com estatísticas, etc.
    return render(request, 'core/home.html')