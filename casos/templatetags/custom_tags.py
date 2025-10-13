from django import template

register = template.Library()

@register.filter
def get_item(container, key):
    """
    Filtro inteligente que acessa um item de um dicionário pela chave
    ou de uma lista pelo índice.
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