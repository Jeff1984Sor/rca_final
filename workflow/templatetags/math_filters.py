# workflow/templatetags/math_filters.py

from django import template

register = template.Library()

@register.filter(name='multiply')
def multiply(value, arg):
    """
    Multiplica o valor (value) pelo argumento (arg).
    Uso: {{ algum_numero|multiply:outro_numero }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''