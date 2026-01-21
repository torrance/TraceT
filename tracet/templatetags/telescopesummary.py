from django import template

register = template.Library()


@register.filter
def telescopesummary(telescope):
    def get_parents(cls):
        parents = [cls]
        for b in cls.__bases__:
            parents.extend(get_parents(b))
        return parents

    if telescope is not None:
        return template.loader.render_to_string(
            [
                f"tracet/telescope/{parent.__name__}.html"
                for parent in get_parents(type(telescope))
            ],
            {"telescope": telescope},
        )
