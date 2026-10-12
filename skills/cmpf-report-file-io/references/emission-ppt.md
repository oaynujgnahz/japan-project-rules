# Emission PPT Output

Use for 排出量結果レポート `.pptx` generation and download.

## Key Files

- Controller: `carbonapi/src/main/java/com/ntt/cmpf/carbonapi/controller/ReportController.java`
- Main service: `carbonapi/src/main/java/com/ntt/cmpf/carbonapi/service/EmissionPptReportService.java`
- PPT services: `carbonapi/src/main/java/com/ntt/cmpf/carbonapi/service/report/`
- DTOs: `ReportOutputInfo`, `GhgPptReportContext`, `EmissionReportDto`, `EmissionSecondReportDto`
- Templates: `carbonapi/src/main/resources/ppt_template/ja/emission_report.pptx`, `carbonapi/src/main/resources/ppt_template/en/emission_report.pptx`
- Frontend: `frontend/src/views/report/reportOutput/index.vue`
- Docs: `docs/报告出力_排出量PPT/`

## Flow

- Frontend calls `/report/downloadPptFile` with report output parameters.
- Backend loads the language-specific official template and updates OOXML slides, tables, charts, and media.
- Slide removal is based on selected report content; do not replace this with alternate partial templates unless the docs/spec changes.

## Invariants

- Template path is `ppt_template/{ja,en}/emission_report.pptx`.
- Response content type is PPTX.
- Filename follows the business language pattern, including company/year context.
- Changes to chart/table generation usually require checking both Java data builders and final slide XML.
- Keep Japanese and English template behavior aligned.

## Verification

Use the acceptance docs when possible. Minimal structural checks:

```bash
unzip -l exported.pptx | rg 'ppt/slides/slide|ppt/media|ppt/charts'
unzip -p exported.pptx ppt/slides/slide2.xml | rg 'Scope|r:embed|a:tbl'
```

Also open/render the PPT when visual layout, fonts, positions, colors, or page deletion changed.

## Searches

```bash
rg -n "downloadPptFile|EmissionPpt|GhgReportPpt|Pptx|ppt_template|ReportOutputInfo" carbonapi/src/main/java frontend/src docs
```
