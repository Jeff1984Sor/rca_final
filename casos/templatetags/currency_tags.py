# casos/templatetags/currency_tags.py

from django import template
from decimal import Decimal, InvalidOperation # Usamos Decimal, que é mais preciso para dinheiro
from django.utils.safestring import mark_safe # Essencial para garantir que o R$ apareça

register = template.Library()

@register.filter(name='currency')
def currency(value):
    """
    Filtro robusto para formatar um valor como moeda no padrão brasileiro (R$).
    Lida com Decimals, floats, ints e strings (com ponto ou vírgula).
    Ex: 10 -> R$ 10,00
    """
    if value is None or value == '':
        return "-" # Retorna um hífen se o valor for vazio

    try:
        # Etapa de "limpeza" do valor para garantir que seja um número válido
        # 1. Converte para string
        # 2. Troca vírgula por ponto para a conversão para Decimal funcionar
        s_value = str(value).replace(',', '.')
        
        # Converte a string limpa para Decimal
        d_value = Decimal(s_value)

        # Arredonda para 2 casas decimais
        quantized_value = d_value.quantize(Decimal('0.01'))

        # Formata a string manualmente para garantir o padrão brasileiro
        # Separa a parte inteira da decimal
        inteiro, decimal = str(quantized_value).split('.')
        
        # Adiciona o separador de milhar
        inteiro_formatado = ""
        for i, char in enumerate(reversed(inteiro)):
            if i > 0 and i % 3 == 0:
                inteiro_formatado = "." + inteiro_formatado
            inteiro_formatado = char + inteiro_formatado
            
        # Junta tudo
        formatted_value = f"{inteiro_formatado},{decimal}"
        
        # Adiciona o "R$" e um espaço não-quebrável, e marca como seguro
        return mark_safe(f"R$&nbsp;{formatted_value}")

    except (InvalidOperation, ValueError, TypeError):
        # Se, mesmo após a limpeza, o valor não for um número, 
        # retorna o valor original sem quebrar a página.
        return value