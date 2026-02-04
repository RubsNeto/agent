from django import template

register = template.Library()

@register.filter(name='split')
def split(value, arg):
    """
    Split a string by a delimiter.
    Usage: {{ string|split:',' }}
    """
    if not value:
        return []
    return value.split(arg)

@register.filter(name='strip')
def strip(value):
    """
    Strip whitespace from a string.
    Usage: {{ string|strip }}
    """
    if not value:
        return value
    return value.strip()
