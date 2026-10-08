"""CSV conversion utilities for File Control."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class CSVConversionError(Exception):
    """Base exception for CSV conversion operations."""

    pass


class CSVConverter:
    """Handle conversions between CSV and other file formats."""

    SUPPORTED_INPUT_FORMATS = {
        ".csv": "CSV File",
        ".xlsx": "Excel Workbook",
        ".xls": "Excel 97-2003 Workbook",
        ".json": "JSON File",
        ".txt": "Text File (tab/comma-delimited)",
        ".tsv": "Tab-Separated Values",
        ".ods": "LibreOffice Spreadsheet",
    }

    SUPPORTED_OUTPUT_FORMATS = {
        ".csv": "CSV File",
        ".xlsx": "Excel Workbook",
        ".json": "JSON File",
        ".pdf": "PDF File",
    }

    def __init__(self, log: Callable[[str], None] | None = None) -> None:
        """Initialize converter with optional logging function."""
        self.log = log or (lambda msg: None)

    def _log(self, message: str) -> None:
        """Internal logging method."""
        self.log(message)

    def convert_to_csv(self, input_file: str, output_file: str | None = None) -> str:
        """
        Convert a file to CSV format.
        
        Args:
            input_file: Path to input file
            output_file: Path to output CSV file (optional, auto-generated if not provided)
            
        Returns:
            Path to the created CSV file
            
        Raises:
            CSVConversionError: If conversion fails
        """
        input_path = Path(input_file)
        
        if not input_path.exists():
            raise CSVConversionError(f"Input file not found: {input_file}")
        
        file_ext = input_path.suffix.lower()
        
        if file_ext not in self.SUPPORTED_INPUT_FORMATS:
            raise CSVConversionError(
                f"Unsupported input format: {file_ext}. "
                f"Supported formats: {', '.join(self.SUPPORTED_INPUT_FORMATS.keys())}"
            )
        
        if output_file is None:
            output_file = str(input_path.with_suffix(".csv"))
        
        self._log(f"Converting {input_path.name} to CSV...")
        
        try:
            if file_ext == ".csv":
                # If already CSV, just copy
                self._copy_file(input_file, output_file)
            elif file_ext in (".xlsx", ".xls", ".ods"):
                self._excel_to_csv(input_file, output_file)
            elif file_ext == ".json":
                self._json_to_csv(input_file, output_file)
            elif file_ext in (".txt", ".tsv"):
                self._text_to_csv(input_file, output_file)
            else:
                raise CSVConversionError(f"Unsupported format: {file_ext}")
            
            self._log(f"Successfully converted to CSV: {output_file}")
            return output_file
            
        except CSVConversionError:
            raise
        except Exception as e:
            raise CSVConversionError(f"Conversion failed: {str(e)}") from e

    def convert_csv_to_format(self, csv_file: str, output_format: str, output_file: str | None = None) -> str:
        """
        Convert a CSV file to another format.
        
        Args:
            csv_file: Path to input CSV file
            output_format: Output format ('.xlsx', '.pdf', '.csv')
            output_file: Path to output file (optional, auto-generated if not provided)
            
        Returns:
            Path to the created file
            
        Raises:
            CSVConversionError: If conversion fails
        """
        input_path = Path(csv_file)
        
        if not input_path.exists():
            raise CSVConversionError(f"Input file not found: {csv_file}")
        
        if input_path.suffix.lower() != ".csv":
            raise CSVConversionError(f"Input file must be CSV format, got {input_path.suffix}")
        
        if output_format not in self.SUPPORTED_OUTPUT_FORMATS:
            raise CSVConversionError(
                f"Unsupported output format: {output_format}. "
                f"Supported formats: {', '.join(self.SUPPORTED_OUTPUT_FORMATS.keys())}"
            )
        
        if output_file is None:
            output_file = str(input_path.with_suffix(output_format))
        
        self._log(f"Converting CSV to {output_format.upper()[1:]}...")
        
        try:
            if output_format == ".csv":
                # If already CSV, just copy
                self._copy_file(csv_file, output_file)
            elif output_format == ".xlsx":
                self._csv_to_excel(csv_file, output_file)
            elif output_format == ".json":
                self._csv_to_json(csv_file, output_file)
            elif output_format == ".pdf":
                self._csv_to_pdf(csv_file, output_file)
            else:
                raise CSVConversionError(f"Unsupported output format: {output_format}")
            
            self._log(f"Successfully converted to {output_format.upper()[1:]}: {output_file}")
            return output_file
            
        except CSVConversionError:
            raise
        except Exception as e:
            raise CSVConversionError(f"Conversion failed: {str(e)}") from e

    # ================================================================ Helpers

    def _copy_file(self, src: str, dst: str) -> None:
        """Copy a file."""
        import shutil
        shutil.copy2(src, dst)

    def _excel_to_csv(self, excel_file: str, csv_file: str) -> None:
        """Convert Excel file to CSV using openpyxl."""
        try:
            import openpyxl
        except ImportError:
            raise CSVConversionError(
                "openpyxl library required for Excel support. "
                "Install it with: pip install openpyxl"
            )
        
        try:
            wb = openpyxl.load_workbook(excel_file, data_only=True)
            ws = wb.active
            
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                for row in ws.iter_rows(values_only=True):
                    writer.writerow(row)
        finally:
            if "wb" in locals():
                wb.close()

    def _json_to_csv(self, json_file: str, csv_file: str) -> None:
        """Convert JSON file to CSV."""
        import json
        
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Assume data is a list of dictionaries
        if not isinstance(data, list):
            if isinstance(data, dict):
                data = [data]
            else:
                raise CSVConversionError("JSON must be an object or array of objects")
        
        if not data:
            raise CSVConversionError("JSON data is empty")
        
        # Get headers from first record
        headers = list(data[0].keys()) if isinstance(data[0], dict) else None
        
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            if headers:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(data)
            else:
                writer = csv.writer(f)
                for record in data:
                    writer.writerow([record] if not isinstance(record, (list, tuple)) else record)

    def _text_to_csv(self, text_file: str, csv_file: str) -> None:
        """Convert tab/comma-delimited text file to CSV."""
        import shutil
        # For TXT/TSV files, we'll try to normalize them to CSV
        with open(text_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Detect delimiter (tab or comma)
        lines = content.split("\n")
        delimiter = "\t" if any("\t" in line for line in lines) else ","
        
        # Read and write as CSV
        with open(text_file, "r", encoding="utf-8", newline="") as infile:
            reader = csv.reader(infile, delimiter=delimiter)
            with open(csv_file, "w", encoding="utf-8", newline="") as outfile:
                writer = csv.writer(outfile)
                writer.writerows(reader)

    def _csv_to_excel(self, csv_file: str, excel_file: str) -> None:
        """Convert CSV file to Excel using openpyxl."""
        try:
            import openpyxl
            from openpyxl.utils.dataframe import dataframe_to_rows
        except ImportError:
            raise CSVConversionError(
                "openpyxl library required for Excel support. "
                "Install it with: pip install openpyxl"
            )
        
        # Read CSV
        data = []
        with open(csv_file, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            data = list(reader)
        
        # Write to Excel
        wb = openpyxl.Workbook()
        ws = wb.active
        
        for row in data:
            ws.append(row)
        
        wb.save(excel_file)
        wb.close()

    def _csv_to_json(self, csv_file: str, json_file: str) -> None:
        """Convert CSV file to JSON."""
        import json

        with open(csv_file, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not reader.fieldnames:
            raise CSVConversionError("CSV file must contain a header row for JSON conversion")

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)

    def _csv_to_pdf(self, csv_file: str, pdf_file: str) -> None:
        """Convert CSV file to PDF using reportlab."""
        try:
            from reportlab.lib import pagesizes
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib import colors
        except ImportError:
            raise CSVConversionError(
                "reportlab library required for PDF support. "
                "Install it with: pip install reportlab"
            )
        
        # Read CSV data
        data = []
        with open(csv_file, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            data = list(reader)
        
        if not data:
            raise CSVConversionError("CSV file is empty")
        
        # Create PDF
        doc = SimpleDocTemplate(pdf_file, pagesize=pagesizes.letter)
        story = []
        
        # Add title
        styles = getSampleStyleSheet()
        title = Paragraph("CSV Data Report", styles["Heading1"])
        story.append(title)
        story.append(Spacer(1, 0.3 * inch))
        
        # Create table
        table = Table(data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                ]
            )
        )
        
        story.append(table)
        
        # Build PDF
        doc.build(story)
