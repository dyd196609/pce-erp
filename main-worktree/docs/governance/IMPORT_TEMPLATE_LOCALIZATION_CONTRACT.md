# Import Template Localization Contract

Authority: `PCE-LATEST-BASE-DATA-TEMPLATE-V1.0` contract revision, 2026-09-11.

All user-visible workbook content is Chinese by default. Worksheet names come from each formal import schema's canonical business label; visible headers come from the same schema field metadata; Boolean and enum displays come from the schema's canonical `choiceLabels`. Business codes, API/database enum codes and machine identities remain unchanged internally.

Permitted English is limited to business codes and identities, approved international unit abbreviations, product/model identifiers, and genuine proper names. Internal field names and raw enum codes must not appear as ordinary user-facing worksheet content.

The backend template generator and parser share this authority. The parser maps Chinese display values back to formal internal codes, while preview/readback maps codes to Chinese display values. No Excel-only translation table and no second base-data template are permitted.

The mandatory build gate is `npm run verify:pce-import-template-localization`. It invokes the actual `FormalImportTemplateView` used by Template Download, saves the exact HTTP response bytes to temporary `.xlsx` files, then opens all nine workbooks and checks response type, ZIP magic, sheet names, headers, localized validations/example values, forbidden technical English, and parser round-trip integrity. A direct generator-only check is insufficient and cannot satisfy this contract.
