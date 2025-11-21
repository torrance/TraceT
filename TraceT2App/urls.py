from django.urls import path
from . import views

urlpatterns = [
    path("notices", views.NoticeList.as_view(), name="notices"),
    path("notices/create", views.NoticeCreate.as_view(), name="noticecreate"),
    path("notices/<int:id>", views.Notice.as_view(), name="notice"),
    path("triggers/create", views.TriggerCreate.as_view(), name="triggercreate"),
    path("triggers/<int:id>", views.Trigger.as_view(), name="trigger"),
    path("triggers/<int:id>/edit", views.TriggerEdit.as_view(), name="triggeredit")
]