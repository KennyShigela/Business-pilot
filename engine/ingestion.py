"""
Data Ingestion Engine for BusinessPilot.
Reads Excel (.xlsx, .xls) and CSV files, extracts sheets, inspects raw rows,
and stages raw data into the database for auditability and schema mapping.
"""
import os
import json
import uuid
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from database.db import execute_write, query_one, generate_uuid, get_connection

# The class below is for reading and inspecting Excel and CSV spreadsheet files
class SpreadsheetReader:
    """Universal reader for Excel and CSV business files."""

    # The function below is for inspecting an uploaded file and returning sheet names, preview rows, and columns
    @staticmethod
    def inspect_file(file_path: str) -> Dict[str, Any]:
        """
        Inspects an uploaded file and returns metadata:
        - filename, extension, file size
        - list of sheet names (for Excel) or single sheet (for CSV)
        - preview of first 5 rows and detected columns per sheet
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_name = os.path.basename(file_path)
        ext = os.path.splitext(file_name)[1].lower()
        file_size = os.path.getsize(file_path)

        sheets_data = {}

        if ext in [".xlsx", ".xls"]:
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names
            for sheet in sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet, nrows=50)
                cleaned_cols = [str(col).strip() for col in df.columns if not str(col).startswith("Unnamed:")]
                preview_rows = df.head(5).fillna("").to_dict(orient="records")
                sheets_data[sheet] = {
                    "total_sample_rows": len(df),
                    "columns": cleaned_cols,
                    "preview": preview_rows,
                }
        elif ext == ".csv":
            for encoding in ["utf-8", "latin-1", "cp1252"]:
                try:
                    df = pd.read_csv(file_path, encoding=encoding, nrows=50)
                    cleaned_cols = [str(col).strip() for col in df.columns if not str(col).startswith("Unnamed:")]
                    preview_rows = df.head(5).fillna("").to_dict(orient="records")
                    sheets_data["Sheet1"] = {
                        "total_sample_rows": len(df),
                        "columns": cleaned_cols,
                        "preview": preview_rows,
                    }
                    break
                except UnicodeDecodeError:
                    continue
        else:
            raise ValueError(f"Unsupported file format: {ext}. Please provide .xlsx, .xls, or .csv")

        return {
            "file_name": file_name,
            "extension": ext,
            "size_bytes": file_size,
            "sheet_count": len(sheets_data),
            "sheets": sheets_data,
        }

    # The function below is for loading an entire sheet from a file into a pandas DataFrame
    @staticmethod
    def load_full_sheet(file_path: str, sheet_name: Optional[str] = None) -> pd.DataFrame:
        """Loads complete sheet data into a pandas DataFrame."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext in [".xlsx", ".xls"]:
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                df = pd.read_excel(file_path)
        elif ext == ".csv":
            df = pd.read_csv(file_path)
        else:
            raise ValueError(f"Unsupported format: {ext}")

        cols_to_keep = [col for col in df.columns if not str(col).startswith("Unnamed:")]
        df = df[cols_to_keep]
        df.columns = [str(col).strip() for col in df.columns]
        return df

# The class below is for managing raw data staging and tracking import audit history
class StagingManager:
    """Manages data_sources, import_jobs, and raw_import_rows."""

    # The function below is for creating an import job tracking record in the database
    @staticmethod
    def create_import_job(company_id: str, file_path: str, source_type: str = "EXCEL") -> Tuple[str, str]:
        """Creates a data_source and an active import_job record."""
        source_id = generate_uuid()
        job_id = generate_uuid()
        file_name = os.path.basename(file_path)

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO data_sources (id, company_id, source_type, name, file_url, status)
                VALUES (?, ?, ?, ?, ?, 'Active');
                """,
                (source_id, company_id, source_type, file_name, file_path),
            )
            conn.execute(
                """
                INSERT INTO import_jobs (id, data_source_id, status, rows_processed, rows_successful, rows_failed)
                VALUES (?, ?, 'PROCESSING', 0, 0, 0);
                """,
                (job_id, source_id),
            )
        return source_id, job_id

    # The function below is for staging raw spreadsheet rows as JSON records for auditability
    @staticmethod
    def stage_raw_dataframe(job_id: str, df: pd.DataFrame) -> int:
        """
        Stores raw rows in JSON format inside raw_import_rows.
        Preserves complete data lineage for troubleshooting.
        """
        records = df.fillna("").to_dict(orient="records")
        staged_count = 0
        with get_connection() as conn:
            for idx, record in enumerate(records, start=1):
                row_id = generate_uuid()
                raw_json = json.dumps(record, default=str)
                conn.execute(
                    """
                    INSERT INTO raw_import_rows (id, import_job_id, row_number, raw_data, validation_status)
                    VALUES (?, ?, ?, ?, 'VALID');
                    """,
                    (row_id, job_id, idx, raw_json),
                )
                staged_count += 1
            conn.execute(
                """
                UPDATE import_jobs SET rows_processed = ? WHERE id = ?;
                """,
                (staged_count, job_id),
            )
        return staged_count
