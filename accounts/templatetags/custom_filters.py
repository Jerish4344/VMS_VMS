from django import template

register = template.Library()

@register.filter
def lookup(dictionary, key):
    """
    Template filter to look up a key in a dictionary
    Usage: {{ dictionary|lookup:key }}
    """
    return dictionary.get(key, {})

@register.filter
def permission_icon(action):
    """
    Template filter to get appropriate FontAwesome icon for permission action
    """
    icons = {
        'view': 'eye',
        'add': 'plus',
        'edit': 'edit',
        'delete': 'trash',
        'export': 'download',
        'manage': 'cogs',
    }
    return icons.get(action, 'key')

@register.filter
def has_permission(user, module_action):
    """
    Template filter to check if a user has a specific permission
    Usage: {{ user|has_permission:'vehicles,add' }}
    """
    if not user.is_authenticated:
        return False
    
    try:
        module_name, action = module_action.split(',')
        return user.has_module_permission(module_name.strip(), action.strip())
    except (ValueError, AttributeError):
        return False

@register.simple_tag
def has_permission_tag(user, module_name, action):
    """
    Template tag to check if a user has a specific permission
    Usage: {% has_permission_tag user 'vehicles' 'add' as can_add_vehicle %}
    """
    if not user.is_authenticated:
        return False
    return user.has_module_permission(module_name, action)
