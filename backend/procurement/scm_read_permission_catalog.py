"""User-approved read-only contract; no new execution or organization grants."""
INQUIRY_READ = "procurement.purchase_inquiry.read"
QUOTATION_READ = "procurement.supplier_quotation.read"
PREPARATION_READ = "procurement.price_approval_preparation.read"
SOURCE_REQUEST_READ = "procurement.purchase_request.view"

READ_PERMISSIONS = (
    (INQUIRY_READ, "采购询价读取", "SCM"),
    (QUOTATION_READ, "供应商报价读取", "SCM"),
    (PREPARATION_READ, "核价准备读取", "SCM"),
)
READ_ROLES = {
    INQUIRY_READ: frozenset({"buyer", "purchase_manager"}),
    QUOTATION_READ: frozenset({"buyer", "purchase_manager"}),
    PREPARATION_READ: frozenset({"purchase_manager"}),
}
ROLE_READ_CODES = {
    "buyer": (INQUIRY_READ, QUOTATION_READ),
    "purchase_manager": (INQUIRY_READ, QUOTATION_READ, PREPARATION_READ),
}
INQUIRY_SCOPE = (INQUIRY_READ, SOURCE_REQUEST_READ)
QUOTATION_SCOPE = (QUOTATION_READ, *INQUIRY_SCOPE)
PREPARATION_SCOPE = (PREPARATION_READ, *QUOTATION_SCOPE)

