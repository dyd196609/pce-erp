from django.urls import path

from .definition_views import (
    ProcessDefinitionAtomicMinimalTemplateView,
    ProcessDefinitionDetailView,
    ProcessDefinitionExecutionResolutionView,
    ProcessDefinitionListView,
    ProcessDefinitionNodesView,
)


urlpatterns = [
    path("definitions/", ProcessDefinitionListView.as_view(), name="workflow-definition-list"),
    path(
        "definitions/atomic-minimal-template/",
        ProcessDefinitionAtomicMinimalTemplateView.as_view(),
        name="workflow-definition-atomic-minimal-template",
    ),
    path(
        "definitions/<int:definition_id>/",
        ProcessDefinitionDetailView.as_view(),
        name="workflow-definition-detail",
    ),
    path(
        "definitions/<int:definition_id>/nodes/",
        ProcessDefinitionNodesView.as_view(),
        name="workflow-definition-nodes",
    ),
    path(
        "definitions/<int:definition_id>/execution-resolution/",
        ProcessDefinitionExecutionResolutionView.as_view(),
        name="workflow-definition-execution-resolution",
    ),
]
