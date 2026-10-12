---
name: cmpf-report-file-io
description: Use when working in CMPF on report/file downloads, exports, templates, Excel or CSV imports, upload validation, generated PPT/PDF/JSON/DOCX files, Content-Disposition handling, or frontend blob save flows.
---

# CMPF Report File IO

## Overview

CMPF file IO changes are usually cross-cutting: backend controller/service/mapper code, classpath templates, frontend blob or upload handling, locale text, and business validation must stay aligned. Use this skill as the entry point, then load only the reference file that matches the format or business area.

## First Pass

Before editing, identify the file flow:

- Direction: download/export, import/upload, template download, stored file download, or generated batch artifact.
- Format: xlsx, csv, pptx, pdf, json, docx, or raw stored binary.
- Business area: PCF, ESG activity volume/item, emission factors, electricity service, public data/GxD, report output, base/site CSV, account/user application, certificate/credit files.
- Surfaces: backend endpoint, service logic, mapper SQL, DTO/model, classpath template, frontend API wrapper, view/component, locale text, and docs.

Use `rg` from the repository root. Good starting searches:

```bash
rg -n "download|export|upload|template|Content-Disposition|application/vnd|\\.xlsx|\\.csv|\\.pptx|\\.pdf" carbonapi/src/main/java frontend/src
rg -n "downloadBlob|FormData|before-upload|accept=|parseContentDispositionFilename" frontend/src
find carbonapi/src/main/resources -type f \( -name '*.xlsx' -o -name '*.pptx' -o -name '*.csv' -o -name '*.html' \)
```

## Load References

- Always read `references/formats.md` for response headers, filename encoding, template packaging, upload validation, and verification checks.
- Read `references/pcf-excel.md` for PCF算定 Excel 取込・出力.
- Read `references/emission-ppt.md` for 排出量結果 PPT output.
- Read `references/esg-excel-csv.md` for ESG activity volume/item, activity CSV, emission factor CSV/XLSX, and base/site CSV flows.
- Read `references/electricity-public-data.md` for 電力データ連携, public data, GxD JSON/CSV, consent/template files, and generated abnormal-list workbooks.

Load only the relevant reference file(s). If the task crosses domains, load each matching reference and keep the change scoped.

## Change Checklist

- Backend endpoint returns the intended type: `ResponseEntity<byte[]>`, `HttpServletResponse`, or structured upload result.
- `Content-Type` matches the real artifact, and `Content-Disposition` uses a safe UTF-8 filename for Japanese company/product names.
- Template paths are classpath resources under `carbonapi/src/main/resources`; Maven packaging must include them.
- Import/upload accepts only the intended extensions and validates sheet name, headers, required cells, row count, duplicate rows, and master-data lookup rules.
- Row-level errors preserve Excel/CSV line numbers where users can fix the file.
- Mapper XML, DTOs, and service logic agree on field names and Java 8-compatible types.
- Frontend API uses blob response for downloads and `FormData` for uploads; views clear stale upload errors before retrying.
- User-visible messages are synchronized across existing locale files where the feature is localized.
- Docs or acceptance checklists are updated when format, template structure, validation, or file naming changes.

## Verification

Prefer the narrowest useful check first:

- Backend compile/test: `./mvn8 -pl carbonapi -am test -DskipTests=false` when Java behavior changed; use package if tests are skipped locally by project default.
- Frontend: `npm run build` from `frontend/` for API/view/upload/download changes.
- Generated files: inspect the actual bytes when possible. For xlsx/pptx, confirm ZIP structure with `unzip -l`; for pptx, inspect target slide XML when layout or chart data changed.
- Manual or integration verification should cover both success download/import and representative validation failure.

## Common Mistakes

- Treating export-only and import-only as separate features when the same template drives both.
- Updating Java generation but forgetting the frontend filename, MIME type, or upload error display.
- Changing template columns without updating parser validation and row-error messages.
- Relying on visual PPT/Excel appearance without checking the zipped OOXML payload.
- Adding Chinese source comments around Japanese business terms; prefer Japanese comments when practical.
