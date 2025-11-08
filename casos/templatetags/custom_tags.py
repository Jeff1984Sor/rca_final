import re
from django import template
from datetime import date

register = template.Library()

@register.filter
def get_item(container, key):
    """
    Acessa um item de um dicionário pela chave ou de uma lista pelo índice.
    """
    if isinstance(container, dict):
        return container.get(key)
    elif isinstance(container, (list, tuple)):
        try:
            index = int(key)
            if 0 <= index < len(container):
                return container[index]
        except (ValueError, TypeError):
            pass
    return None



@register.filter(name='add_class')
def add_class(field, css_class):
    """
    Aplica a classe CSS ao campo do formulário.
    """
    try:
        return field.as_widget(attrs={"class": css_class})
    except Exception:
        return field



@register.filter(name='add_error_class')
def add_error_class(field):
    """
    Retorna 'is-invalid' se o campo tiver erros, senão retorna string vazia.
    """
    try:
        return "is-invalid" if field.errors else ""
    except AttributeError:
        return ""



@register.filter(name='input_class')
def input_class(field):
    """
    Retorna 'form-control' ou 'form-control is-invalid' dependendo dos erros.
    """
    try:
        return "form-control is-invalid" if field.errors else "form-control"
    except AttributeError:
        return "form-control"



@register.filter(name='split_linebreaks')
def split_linebreaks(value):
    """
    Divide uma string por quebras de linha (\n ou <br>) para criar uma lista.
    """
    if not value:
        return []
    return re.split(r'\s*(?:\n|<br\s*/?>)+\s*', str(value).strip())

@register.filter
def days_until(value):
    """
    Calcula o número de dias restantes de hoje até uma data futura ('value').
    Retorna um número inteiro.
    """
    if not isinstance(value, date):
        # Se o valor não for uma data, não podemos calcular
        return None
    
    today = date.today()
    delta = value - today
    return delta.days

@register.filter
def abs_value(value):
    """Retorna o valor absoluto (positivo) de um número."""
    try:
        return abs(value)
    except (ValueError, TypeError):
        return value # Retorna o valor original se não for um número