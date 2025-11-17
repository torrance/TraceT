from django.urls import path
from . import views

urlpatterns = [
    path("events", views.EventList.as_view(), name="events"),
    path("events/create", views.EventCreate.as_view(), name="eventcreate"),
    path("events/<int:id>", views.Event.as_view(), name="event"),
    path("triggers/create", views.TriggerCreate.as_view(), name="triggercreate"),
    path("triggers/<int:id>", views.Trigger.as_view(), name="trigger"),
    path("triggers/<int:id>/edit", views.TriggerEdit.as_view(), name="triggeredit")
]