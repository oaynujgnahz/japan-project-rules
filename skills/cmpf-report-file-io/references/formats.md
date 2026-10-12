# Common Formats

## Current Format Map

| Format | Typical CMPF use | Notes |
| --- | --- | --- |
| xlsx | PCF Excel, ESG templates, electricity templates, abnormal-list workbook | Usually template-based; verify sheet names and hidden/reference sheets. |
| csv | Activity volume, activity item, emission factor, base/site, public data history | Header order and encoding matter; row numbers must match user-visible CSV lines. |
| pptx | 排出量結果レポート | OOXML ZIP package; changes often require inspecting slide XML. |
| pdf | Consent files, uploaded evidence, Excel-to-PDF related output | Distinguish stored PDF download from generated PDF. |
| json | GxD / PCF receive-history style downloads | Preserve exact payload and filename behavior. |
| docx | Electricity consent/template downloads | Treat as stored/template binary unless generation logic is present. |

## Backend Response Rules

- Use the MIME type that matches the actual artifact.
- For Japanese filenames, prefer UTF-8-safe `Content-Disposition`; check existing local helpers before adding new ones.
- For stored files, preserve the uploaded filename unless the business spec requires a generated name.
- For generated files, centralize filename generation when a domain already has a builder/helper.
- Do not stream a template resource directly if the service is expected to populate workbook/sheet data first.

Common MIME values:

```text
xlsx: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
pptx: application/vnd.openxmlformats-officedocument.presentationml.presentation
docx: application/vnd.openxmlformats-officedocument.wordprocessingml.document
csv: text/csv or application/octet-stream, following the existing endpoint pattern
pdf: application/pdf
json: application/json
```

## Import and Upload Rules

- Validate extension in both frontend and backend; frontend checks are UX, backend checks are authority.
- For Excel, validate workbook open failure, exact sheet names, required headers, hidden columns if used, and max rows.
- For CSV, validate header count/order, blank required values, type/format, duplicate business keys, and row limit.
- Return row-level errors with line number when the user can fix the uploaded file. Use whole-file errors for missing sheet/header or unreadable files.
- Keep parser DTO fields aligned with template column order and business language.

## Frontend Rules

- Downloads should request blob/arraybuffer and save using backend `Content-Disposition` when available.
- Uploads should use `FormData`; include the same contextual parameters as the download/template that produced the file.
- Clear old upload errors before a new upload.
- Show only a bounded number of row errors when surrounding UI already follows that pattern.
- Keep `.xlsx`, `.xls`, `.csv`, `.pdf` accept filters synchronized with backend validation.

## Verification

- Confirm `target/classes` contains new or changed classpath templates after Maven packaging.
- For xlsx/pptx/docx, use `unzip -l file` to verify package structure.
- For generated pptx, inspect `ppt/slides/slideN.xml` and related `ppt/media` entries when slide content changed.
- For CSV, inspect actual delimiter, newline, header order, and Japanese text rendering.
