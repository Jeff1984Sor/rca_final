from django import template

register = template.Library()

@register.filter(name='add_class')
def add_class(value, arg):
    """
    Adiciona uma classe CSS a um campo de formulário
    Uso: {{ field|add_class:'form-control' }}
    """
    css_classes = value.field.widget.attrs.get('class', '')

    # Garante que a nova classe não será duplicada
    if css_classes:
        css_classes = css_classes.split(' ')
    else:
        css_classes = []

    # Adiciona a nova classe, evitando duplicatas
    if arg not in css_classes:
        css_classes.append(arg)

    return value.as_widget(attrs={'class': ' '.join(css_classes)})