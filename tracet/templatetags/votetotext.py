from django import template

register = template.Library()


@register.simple_tag
def votetotext(vote):
    if vote == 1:
        return "pass"
    if vote == 0:
        return "maybe"
    if vote == -1:
        return "fail"