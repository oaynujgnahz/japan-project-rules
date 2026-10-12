# Electricity, Public Data, and Stored File IO

Use for 電力データ連携 templates/uploads/downloads, public data/GxD generated files, JSON/CSV downloads, and stored binary downloads.

## Electricity Service

Key files:

- Controller/service: `ElectricityServiceApplicationController.java`, `ElectricityServiceApplicationService.java`
- Templates: `carbonapi/src/main/resources/template/electricity/electricity_application_template.xlsx`, `electricity_cancellation_template.xlsx`
- Frontend API/view: `frontend/src/apis/electricityApi.ts`, `frontend/src/views/data/electricityServiceApplication/index.vue`
- Requirement docs under `carbonapi/新需求/` and `carbonapi/新的画面和后台需求/`

Important flows:

- Template download: `/electricity/templateFileDownload`
- Previous consent download: `/electricity/downloadPreviousConsent`
- Excel upload for location/application data and PDF upload for consent/evidence have different accepted extensions.
- Keep application vs cancellation template behavior separate.

## Public Data and GxD

Key files:

- GxD controller/service: `GxdController.java`, `GxdService.java`
- Public data services: `PublicDataProcessService.java`, `PublicDataHistoryProcessService.java`
- Frontend API: `frontend/src/apis/supplierApi.ts` for `gxd/downloadJsonFile`
- DTOs: `PersonalDataPowerHistoryCsvDto`, GxD search/history DTOs

Important behavior:

- Public data may generate CSV history files and upload them to Azure storage.
- Abnormal-list Excel generation should match the business workbook format and filename pattern.
- JSON downloads should preserve the raw business payload unless the endpoint explicitly wraps it.

## Stored File Downloads

Examples:

- `CertificateCreditViewController` / `CertificateCreditViewService`
- `CfpCalculationLogicSettingController` stored file download
- `FileService` Azure blob download helper

Rules:

- Distinguish generated artifacts from stored uploaded files.
- Preserve authorization/company checks before returning stored bytes.
- Preserve stored filename and extension unless the business flow generates a new name.

## Searches

```bash
rg -n "templateFileDownload|downloadPreviousConsent|downloadJsonFile|PersonalDataPowerHistory|abnormal|異常|downloadFile|Azure|Blob" carbonapi/src/main/java frontend/src carbonapi/新需求 carbonapi/新的画面和后台需求
```
