from django.utils.html import escape
from django.utils.safestring import mark_safe


class Vote:
    def __init__(self, description=""):
        self.inherited = False
        self.description = description

    def __add__(self, other):
        if not isinstance(self, Error) and isinstance(other, Error):
            self.inherited = True
            self.description = other.description
            return self
        else:
            return other

    def __str__(self):
        if self.inherited:
            return f"{self.label} (Inherited)"
        else:
            return self.label

    def __bool__(self):
        return False

    def clear(self):
        self.description = ""
        return self

    def html(self):
        inherited = "inherited" if self.inherited else ""
        return mark_safe(
            f'<span class="vote {self.label.lower()} {inherited}" title="{escape(self.description)}"></span>'
        )


class Error(Vote):
    label = "Error"

    def __lt__(self, other):
        return True


class Fail(Vote):
    label = "Fail"

    def __lt__(self, other):
        if isinstance(other, Error):
            return False
        else:
            return True


class Maybe(Vote):
    label = "Maybe"

    def __lt__(self, other):
        if isinstance(other, Error) or isinstance(other, Fail):
            return False
        else:
            return True


class Pass(Vote):
    label = "Pass"

    def __lt__(self, other):
        return False

    def __bool__(self):
        return True
