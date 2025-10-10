from django.shortcuts import render

# Create your views here.
# clientes/views.py
from django.shortcuts import render
from .models import Cliente

def lista_clientes(request):
    clientes = Cliente.objects.all().order_by('nome') # Pega todos os clientes e ordena por nome
    context = {
        'clientes': clientes
    }
    return render(request, 'clientes/lista_clientes.html', context)