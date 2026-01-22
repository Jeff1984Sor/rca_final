# casos/templatetags/custom_tags.py

import re
from decimal import Decimal, InvalidOperation
from django import template
from datetime import date, datetime
import locale
from django.utils.safestring import mark_safe

register = template.Library()

# --- Configuração de Locale ---
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil.1252')
    except locale.Error:
        print("Aviso: Locale 'pt_BR' não encontrado.")

# ==============================================================================
# ✅ NOVOS FILTROS FALTANTES (get_input_type e get_form_value)
# ==============================================================================
@register.filter(name='get_input_type')
def get_input_type(field_type):
    """Converte o tipo de campo customizado para um tipo de input HTML."""
    mapping = {
        'TEXTO': 'text',
        'NUMERO': 'number',
        'DATA': 'date',
        'MOEDA': 'text', # Usamos 'text' para formatar com máscara no futuro
        'TEXTO_LONGO': 'textarea',
        'BOOLEANO': 'checkbox',
    }
    return mapping.get(field_type, 'text')

@register.filter(name='get_form_value')
def get_form_value(value, field_type):
    """Formata o valor para ser usado em um input de formulário."""
    if value is None:
        return ""
    if field_type == 'DATA':
        try:
            # Tenta converter de string 'YYYY-MM-DD' para objeto date
            date_obj = datetime.strptime(str(value), '%Y-%m-%d').date()
            return date_obj.strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            # Se já for um objeto de data
            if hasattr(value, 'strftime'):
                return value.strftime('%Y-%m-%d')
    return value


# ==============================================================================
# FILTROS JÁ EXISTENTES
# ==============================================================================

@register.filter(name='get_event_color')
def get_event_color(event_type):
    colors = { 'CRIACAO_CASO': 'linear-gradient(135deg, #667eea, #764ba2)', 'MUDANCA_FASE_WF': 'linear-gradient(135deg, #4facfe, #00f2fe)', 'ACAO_WF_CONCLUIDA': 'linear-gradient(135deg, #11998e, #38ef7d)', 'ANDAMENTO': 'linear-gradient(135deg, #f093fb, #f5576c)', 'TIMESHEET': 'linear-gradient(135deg, #8BC34A, #CDDC39)', 'ACORDO': 'linear-gradient(135deg, #FF9800, #FFC107)', 'DESPESA': 'linear-gradient(135deg, #f44336, #e91e63)', 'default': 'linear-gradient(135deg, #9E9E9E, #607D8B)' }
    return colors.get(event_type, colors['default'])

@register.filter(name='get_event_icon')
def get_event_icon(event_type):
    icons = { 'CRIACAO_CASO': '<i class="fa-solid fa-star"></i>', 'MUDANCA_FASE_WF': '<i class="fa-solid fa-route"></i>', 'ACAO_WF_CONCLUIDA': '<i class="fa-solid fa-check-double"></i>', 'ANDAMENTO': '<i class="fa-solid fa-pencil"></i>', 'TIMESHEET': '<i class="fa-solid fa-clock"></i>', 'ACORDO': '<i class="fa-solid fa-handshake"></i>', 'DESPESA': '<i class="fa-solid fa-dollar-sign"></i>', 'default': '<i class="fa-solid fa-circle-info"></i>' }
    return mark_safe(icons.get(event_type, icons['default']))

@register.filter(name='format_dynamic_value')
def format_dynamic_value(value, field_type):
    if value is None or value == '': return "-"
    if field_type == 'MOEDA':
        try:
            return locale.currency(float(value), grouping=True)
        except (ValueError, TypeError):
            formatted = _format_currency_br(value)
            return formatted if formatted is not None else value
    if field_type == 'DATA':
        try:
            date_obj = datetime.strptime(str(value), '%Y-%m-%d').date()
            return date_obj.strftime('%d/%m/%Y')
        except (ValueError, TypeError):
            if hasattr(value, 'strftime'): return value.strftime('%d/%m/%Y')
            return value
    return value

def _format_currency_br(value):
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    raw = raw.replace('R$', '').replace(' ', '')
    raw = re.sub(r'[^0-9,.\-]', '', raw)
    if not raw:
        return None
    if ',' in raw and '.' in raw:
        raw = raw.replace('.', '').replace(',', '.')
    elif ',' in raw:
        raw = raw.replace('.', '')
        if raw.count(',') > 1:
            parts = raw.split(',')
            raw = ''.join(parts[:-1]) + '.' + parts[-1]
        else:
            raw = raw.replace(',', '.')
    elif raw.count('.') > 1:
        parts = raw.split('.')
        raw = ''.join(parts[:-1]) + '.' + parts[-1]
    try:
        num = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None
    sign = '-' if num < 0 else ''
    num = abs(num).quantize(Decimal('0.01'))
    int_part = int(num)
    dec_part = f"{num:.2f}".split('.')[1]
    int_str = f"{int_part:,}".replace(',', '.')
    return f"{sign}R$ {int_str},{dec_part}"

@register.filter
def get_item(container, key):
    if isinstance(container, dict): return container.get(key)
    if isinstance(container, (list, tuple)):
        try:
            index = int(key)
            if 0 <= index < len(container): return container[index]
        except (ValueError, TypeError): pass
    return None

@register.filter(name='add_class')
def add_class(field, css_class):
    try: return field.as_widget(attrs={"class": css_class})
    except Exception: return field

@register.filter(name='add_error_class')
def add_error_class(field):
    return "is-invalid" if hasattr(field, 'errors') and field.errors else ""

@register.filter(name='input_class')
def input_class(field):
    base_class = "form-control"
    if hasattr(field, 'errors') and field.errors: return f"{base_class} is-invalid"
    return base_class

@register.filter(name='split_linebreaks')
def split_linebreaks(value):
    if not value: return []
    return re.split(r'\s*(?:\n|<br\s*/?>)+\s*', str(value).strip())

@register.filter
def days_until(value):
    if not isinstance(value, date): return None
    return (value - date.today()).days

@register.filter
def abs_value(value):
    try: return abs(value)
    except (ValueError, TypeError): return value
