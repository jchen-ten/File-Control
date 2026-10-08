# CSV Converter - User Guide

## Main Menu

When you launch the application, you'll see a **Main Menu** with two options:

### Option 1: File Control
**Organize and compress files**
- Analyze folders or ZIP archives
- Filter files by type and size
- Identify unsupported file formats
- Create compressed ZIP archives automatically
- All files are preserved in a structured output folder

### Option 2: CSV Converter
**Convert between file formats**
- Convert various formats **to CSV**
- Convert CSV files **to Excel or PDF**
- Simple, intuitive interface
- Real-time progress tracking

---

## CSV Converter Guide

### Starting CSV Converter
1. Click the green **"2. CSV Converter"** button on the main menu
2. The CSV Converter window opens

### Conversion Type

At the top, choose what you want to do:

#### Option A: Convert to CSV
**Convert any supported file format to CSV**

1. Select **"Convert to CSV"** radio button
2. Click **"Browse…"** to select your input file
3. Click **"Convert"**
4. Your CSV file is created in the same folder as the input file

**Supported Input Formats:**
- Excel files: `.xlsx`, `.xls`
- JSON files: `.json`
- Text files: `.txt`, `.tsv`
- LibreOffice: `.ods`
- CSV files: `.csv`

#### Option B: Convert from CSV
**Convert a CSV file to Excel or PDF**

1. Select **"Convert from CSV"** radio button
2. Click **"Browse…"** to select your CSV file
3. Choose output format from the dropdown:
   - **Excel (.xlsx)** — Spreadsheet format
   - **PDF (.pdf)** — Document format
4. Click **"Convert"**
5. Your converted file is created in the same folder as the input CSV

---

## File Naming

- Output files are automatically named based on the input file
- Example: `data.csv` → converts to → `data.xlsx` or `data.pdf`
- If the output file already exists, it will be overwritten

---

## Troubleshooting

### "openpyxl library required for Excel support"
**Error:** You're trying to convert an Excel file but the library isn't installed

**Solution:** Open PowerShell and run:
```powershell
pip install openpyxl
```

### "reportlab library required for PDF support"
**Error:** You're trying to convert to PDF but the library isn't installed

**Solution:** Open PowerShell and run:
```powershell
pip install reportlab
```

### "Input file not found"
**Error:** The file path is incorrect or the file was moved/deleted

**Solution:** 
- Click "Browse…" button to select the file again
- Make sure the file exists and hasn't been moved

### "Unsupported input format"
**Error:** The file format is not supported for conversion

**Solution:** 
- Check the supported formats listed in the application
- Convert your file to a supported format first using another tool

### File appears unchanged after conversion
**Possible causes:**
- Check the file location — output is created next to the input file
- The file was successfully converted to the same name (e.g., CSV to CSV)
- Check the Log panel for any warning messages

---

## Tips & Best Practices

1. **Before Converting:**
   - Ensure your input file is properly formatted
   - Make sure you have write permissions in the folder where the file is located
   - For large files, allow extra time for conversion

2. **CSV Format:**
   - CSV files should have consistent columns across rows
   - The first row is treated as data (not headers in all cases)
   - Special characters in CSV are handled automatically

3. **Excel Output:**
   - Data is formatted with a header row in light grey
   - All data is in the first sheet (worksheet)
   - Numbers are preserved as numbers, not text

4. **PDF Output:**
   - Large CSV files may create multiple pages
   - Tables automatically format with headers and grid lines
   - Best results with tables that fit on standard letter size paper

---

## System Requirements

- Windows 7 or later
- .NET Framework (if running executable)
- Python 3.8+ (if running from source)

## Optional Dependencies

For full functionality, install:
```powershell
pip install openpyxl reportlab
```

- Without `openpyxl`: Cannot convert Excel or ODS files
- Without `reportlab`: Cannot convert to PDF format
