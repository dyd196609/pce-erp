# Base Data Row Selection Contract

The shared `PceEnterpriseListTable` owns selection behavior for every latest-template consumer.

- A row checkbox changes only that row and selected count by one.
- A second row checkbox produces a count of two; deselecting one leaves the other selected.
- Only the header checkbox selects or clears all rows in the current visible page/scope.
- Selection is UI state only and invokes no business write API.
- Row identity uses the configured `rowKey`; when it is absent in provider rows, the shared table falls back to the canonical primary business field. Object-reference fallback is used only when neither exists.

This prevents rows without a generic `id`—including Supplier facts—from collapsing to the same Element Plus identity. The contract is shared; no Supplier-only patch exists.
