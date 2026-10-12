# ESG Excel and CSV Imports/Exports

Use for ESG activity volume/item templates, CSV upload/download, emission factor CSV/XLSX, and base/site CSV flows.

## Key Areas

- Activity CSV controller/service: `ActivityCsvController.java`, `ActivityCsvService.java`
- Base CSV controller/service: `BaseCsvController.java`, `BaseCsvService.java`
- ESG activity volume service/controller: `EsgActivityVolumeService.java`, `EsgActivityVolumeController.java`
- ESG activity item service/controller: `EsgActivityItemService.java`, `EsgActivityItemController.java`
- CSV helpers/DTOs: `CSVUtils`, `CSVCodeMessage`, `CSVExceptionBean`, `CSVObjectBean`, `*CSVBean`, `Csv*Dto`
- Templates:
  - `carbonapi/src/main/resources/xls_template/{ja,en}/esg_activity_import_file.xlsx`
  - `carbonapi/src/main/resources/xls_template/{ja,en}/esg_activity_item_list.xlsx`
  - `carbonapi/src/main/resources/xls_template/{ja,en}/activity_item_csv_tpl.xlsx`
  - `carbonapi/src/main/resources/xls_template/{ja,en}/emission_factor_csv_tpl.xlsx`
- Frontend examples:
  - `frontend/src/views/esgActivityVolumeLogin/volumeImportExportModal.vue`
  - `frontend/src/views/esgActivityProjectSetting/importExportModal.vue`
  - `frontend/src/views/data/activityVolume/`
  - `frontend/src/views/data/activityItem/`
  - `frontend/src/views/selfCompany/components/base/upLoadBase.vue`

## Patterns

- Many CSV uploads return `capturedExceptions`, `exceptionTotal`, and `hiddenColume`; preserve frontend display behavior.
- Some templates are xlsx even when the business label says CSV template; follow the existing endpoint/template behavior unless the spec requires a change.
- Locale messages often live in backend i18n resources for CSV validation; do not hard-code new user-facing Japanese text when a message key pattern exists.
- Admin/company context can alter export rows and validation rules.

## When Changing Upload Validation

- Keep frontend `accept` filters, backend extension checks, parser header checks, row-count limits, and i18n messages aligned.
- Preserve line numbers and hidden-column behavior expected by existing upload modals.
- Add or update validation examples in nearby docs if the change is business-visible.

## Searches

```bash
rg -n "CSV|csv|uploadEsgActivity|downloadEsgActivity|downloadActivityItemTemplateFile|downloadBaseUploadFile|capturedExceptions|hiddenColume" carbonapi/src/main/java frontend/src
```
