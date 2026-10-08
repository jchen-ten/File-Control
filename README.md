# File Control

A versatile file management application with two main functions:

1. **File Control** — checks a **folder** or a **zip**: it recursively scans every
   subfolder and nested archive, checks the **format** and **size** of each file,
   isolates the ones that break the rules, then compresses the rest into one or more
   zip archives.

2. **CSV Converter** — converts files between multiple formats:
   - Convert **to CSV** from: Excel (.xlsx, .xls), JSON, Text/TSV, LibreOffice (.ods)
   - Convert **from CSV** to: Excel (.xlsx), PDF

## How it works

The processing runs in **two steps**:

1. **Analysis** — recursive scan of folders and zips (nested zips are extracted and
   analyzed in turn). For each file:
   - unsupported format **or** size above the limit → listed as rejected and copied
     into `rejected/` (the original tree structure is preserved);
   - if only the format is unsupported and a conversion is possible (e.g. OpenOffice
     → Office), the file is converted and accepted;
   - otherwise → added to the compression queue.
2. **Confirmation** — the program shows the list of unsupported files and asks
   whether to create the archives.
3. **Compression** (only after confirmation) — the accepted files are compressed
   into `archives/`. If the size exceeds an archive's limit, several zips are created
   (`archive_001.zip`, `archive_002.zip`, …).

The input folder or zip is **never modified**.

The output is created automatically in a `<name>_NEW` folder located next to the
input (no output path to pick).

## Usage

### Standalone executable (no Python required)

Build the executable once:

```powershell
powershell -ExecutionPolicy Bypass -File build_exe.ps1
```

This produces `dist\FileControl.exe`. Copy the whole `dist` folder (which contains
`FileControl.exe` and `config.json`) to any Windows machine and double-click the
executable — no Python or VS Code needed. See `dist\README.txt` for end-user notes.

### Graphical interface

```powershell
python main.py
```

When launched, you'll see a **main menu** with two options:

#### 1. File Control
Select the input (folder or zip), adjust the settings if needed, then click
**Start check**. After the analysis you are asked whether to create the archives.

#### 2. CSV Converter
Select a file to convert:
- **Convert to CSV**: Choose any supported input file (Excel, JSON, Text, etc.) to convert to CSV
- **Convert from CSV**: Choose a CSV file and select output format (Excel .xlsx or PDF)

The converted file is created automatically next to the input file.

### Command line

```powershell
python main.py "C:\path\to\input"
```

The tool analyzes the input, lists the unsupported files, then asks for confirmation
before creating the zip(s).

## Requirements

For the **CSV Converter** to work with all formats, install optional dependencies:

```powershell
pip install openpyxl reportlab
```

- **openpyxl**: Required for Excel (.xlsx) conversion support
- **reportlab**: Required for PDF conversion support

Without these, CSV Converter will show an error when attempting to use unsupported formats.

## Configuration (`config.json`)

| Key | Description |
| --- | --- |
| `allowed_extensions` | List of allowed extensions (without the dot). |
| `max_file_size_mb` | Maximum size of an allowed file, in MB. |
| `max_zip_size_mb` | Maximum size of an archive before splitting, in MB. |
| `recurse_zips` | `true` to explore the content of nested zips. |
| `convert_unsupported` | `true` to convert unsupported formats when possible. |
| `archive_prefix` | Prefix of the generated archive names. |

## Result

```
<name>_NEW/
├── rejected/            # excluded files (format or size), tree structure preserved
├── archives/            # archive_001.zip, archive_002.zip, ...
└── rejects_report.csv   # list of rejected files
```

### Rejects report (`rejects_report.csv`)

A CSV file (delimiter `;`, UTF-8 with BOM for Excel) listing each rejected file with:

| Column | Description |
| --- | --- |
| File name | Name of the rejected file. |
| Format | Extension (or "(no extension)"). |
| Size (MB) | Size in megabytes. |
| Size (bytes) | Exact size in bytes. |
| Original path | Location inside the input folder/zip. |
| Rejection reason | Unsupported format and/or size exceeded. |

## Format conversion (optional)

Converting OpenOffice formats (`.odt`, `.ods`, `.odp`, …) to Office formats
(`.docx`, `.xlsx`, `.pptx`) requires **LibreOffice** installed on the machine
(the `soffice` executable). Without it, those files are simply rejected.

No other external dependency: everything relies on the Python 3.10+ standard library.
