from django.urls import path
from . import views

urlpatterns = [
    path("", views.Home.as_view(), name="home"),

    path("notices/", views.NoticeList.as_view(), name="notices"),
    path("notices/create/", views.NoticeCreate.as_view(), name="noticecreate"),
    path("notices/<int:id>/", views.Notice.as_view(), name="notice"),

    path("observations/", views.ObservationList.as_view(),name="observations"),
    path("observations/<int:id>/", views.ObservationView.as_view(), name="observationview"),

    path("triggers/", views.TriggerList.as_view(), name="triggers"),
    path("triggers/create/", views.TriggerCreate.as_view(), name="triggercreate"),
    path("triggers/<int:id>/", views.TriggerView.as_view(), name="triggerview"),
    path("triggers/<int:id>/update/", views.TriggerUpdate.as_view(), name="triggeredit"),
    path("triggers/<int:id>/delete/", views.TriggerDelete.as_view(), name="triggerdelete"),
]