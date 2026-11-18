from django.urls import include, path

urlpatterns = [
    path("api/", include("system.urls")),
    path("api/scm/purchase-reconciliations/", include("reconciliation.urls")),
    path("api/scm/purchase-invoice-prepares/", include("purchase_invoice_prepare.urls")),
    path(
        "api/scm/purchase-accounts-payable-drafts/",
        include("purchase_accounts_payable_draft.urls"),
    ),
    path("api/pce/purchase-canary/", include("purchase_canary.urls")),
]
