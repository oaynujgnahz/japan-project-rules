# PCF Excel Import and Export

Use for PCF算定 Excel 取込・出力 around the footprint calculation logic setting screen.

## Key Files

- Backend controller: `carbonapi/src/main/java/com/ntt/cmpf/carbonapi/controller/PcfCalculationExcelController.java`
- Backend services: `carbonapi/src/main/java/com/ntt/cmpf/carbonapi/service/excel/`
- Lookup mapper: `carbonapi/src/main/resources/mapper/PcfCalculationExcelLookupMapper.xml`
- Related mapper: `carbonapi/src/main/resources/mapper/PcfCalculationLogicSettingTblSepcMapper.xml`
- Template: `carbonapi/src/main/resources/pcf_excel_template/PCF算定データ取込・出力-フォーマット.xlsx`
- Frontend API: `frontend/src/apis/pcfCalculationLogicSettingApi.ts`
- Frontend view/modal: `frontend/src/views/setting/footprint/index.vue`, `ImportExportModal.vue`
- Docs: `docs/PCF算定_Excel取込出力_設計書.md`, `docs/PCF算定_Excel取込_表格チェック一覧.md`

## Flow

- Template download: `GET /api/pcf_calculation_logic_setting/excel/template/download`
- Existing data download: `GET /api/pcf_calculation_logic_setting/excel/data/download`
- Import: `POST /api/pcf_calculation_logic_setting/excel/upload`

The import flow combines current Step1 screen state with Excel rows. Do not assume the uploaded file contains every setting field.

## Invariants

- Import reads the exact sheet name `PCF活動量情報`.
- New and edit imports differ: edit import replaces apportionment rows rather than applying a fine-grained diff.
- Download filenames include company/product context; keep Japanese filenames UTF-8-safe.
- `PcfExcelImportRowErrorDto` style row errors are user-facing and should keep Excel row numbers.
- Lookup SQL must stay aligned with activity item, emission factor, base, and existing PCF item sheets.

## When Changing Columns

- Update workbook builder/composer, parser, row DTOs, validation messages, frontend error display if affected, and the design/checklist docs.
- Validate both blank template download and existing-data download.
- Validate upload success and at least one row-level failure.

## Searches

```bash
rg -n "PcfCalculationExcel|PcfExcel|PCF活動量情報|template/download|data/download|excel/upload" carbonapi/src/main/java carbonapi/src/main/resources frontend/src docs
```
