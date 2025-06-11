# Buat file: your_app/templatetags/dict_extras.py
from django import template

register = template.Library()

@register.filter
def lookup(dictionary, key):
    """
    Template filter untuk mengakses dictionary value by key
    Usage: {{ dict|lookup:key }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''

@register.filter 
def get_item(dictionary, key):
    """
    Alternative filter name
    Usage: {{ dict|get_item:key }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''

@register.filter(name='get_at_index')
def get_at_index(list_data, index):
    """
    Mengambil elemen dari list pada index tertentu.
    Contoh penggunaan di template: {{ my_list|get_at_index:0 }}
    """
    try:
        return list_data[index]
    except (IndexError, TypeError):
        # Mengembalikan None atau string kosong jika index tidak valid atau list tidak ada
        return ''
