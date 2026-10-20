import re
import csv
import io
import logging
from typing import Dict, Any, List, Optional, Tuple
import httpx
from openai import AsyncOpenAI
from app.core.config import settings
from app.services.local_db import local_db_service

logger = logging.getLogger(__name__)

# Block any SQL commands that could modify or delete data
FORBIDDEN_SQL_PATTERNS = [
    r"\bdrop\b", r"\bdelete\b", r"\bupdate\b", r"\binsert\b",
    r"\balter\b", r"\btruncate\b", r"\bcreate\b", r"\battach\b",
    r"\bdetach\b", r"\bpragma\b", r"\bexecute\b", r"\bexec\b"
]


class TextToSQLService:
    """
    Learning Note (Module 7 - Text-to-SQL Tool):
    This tool lets the AI answer counting/statistics questions (like "How many documents or chunks
    do we have?" or querying uploaded CSV files) by generating a safe SELECT query and running it
    against our local SQLite database (legal_rag.db).
    """
    def __init__(self):
        # Share the persistent SQLite connection from local_db_service
        self.conn = local_db_service.conn

        self.client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY or "ollama",
            timeout=httpx.Timeout(45.0, connect=5.0),
        )
        self.model = settings.LLM_MODEL

    def sync_csv_table(self, filename: str, content_bytes: bytes) -> Optional[str]:
        """If the user uploads a CSV file, also create a SQLite table for it so it can be queried via SQL."""
        try:
            raw_name = filename.rsplit(".", 1)[0]
            table_name = re.sub(r"\W+", "_", raw_name).strip("_").lower()
            if not table_name or table_name in ("documents", "document_chunks", "threads", "messages"):
                table_name = f"csv_{table_name or 'data'}"

            text_stream = io.StringIO(content_bytes.decode("utf-8", errors="ignore"))
            reader = csv.reader(text_stream)
            headers = next(reader, None)
            if not headers:
                return None

            clean_cols = []
            for idx, h in enumerate(headers):
                cleaned = re.sub(r"\W+", "_", h.strip()).strip("_").lower()
                clean_cols.append(cleaned if cleaned else f"col_{idx+1}")

            cursor = self.conn.cursor()
            cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
            cols_def = ", ".join(f'"{c}" TEXT' for c in clean_cols)
            cursor.execute(f"CREATE TABLE {table_name} ({cols_def});")

            placeholders = ", ".join("?" for _ in clean_cols)
            insert_sql = f"INSERT INTO {table_name} VALUES ({placeholders});"
            for row in reader:
                if len(row) < len(clean_cols):
                    row += [""] * (len(clean_cols) - len(row))
                cursor.execute(insert_sql, row[:len(clean_cols)])

            self.conn.commit()
            logger.info(f"Saved CSV table '{table_name}' into local SQLite database.")
            return table_name
        except Exception as e:
            logger.warning(f"Failed to create CSV SQLite table: {e}")
            return None

    def sync_excel_tables(self, filename: str, content_bytes: bytes) -> List[str]:
        """If the user uploads an Excel (.xlsx) spreadsheet, sync its worksheets into SQLite tables."""
        created_tables: List[str] = []
        try:
            from app.services.document_parser import extract_rows_from_xlsx
            sheets_data = extract_rows_from_xlsx(content_bytes)
            base_name = re.sub(r"\W+", "_", filename.rsplit(".", 1)[0]).strip("_").lower() or "xlsx_data"

            cursor = self.conn.cursor()
            for sheet_name, rows in sheets_data.items():
                if len(rows) < 2:
                    continue
                headers = rows[0]
                clean_sheet = re.sub(r"\W+", "_", sheet_name).strip("_").lower()
                table_name = f"{base_name}_{clean_sheet}" if len(sheets_data) > 1 else base_name
                if table_name in ("documents", "document_chunks", "threads", "messages"):
                    table_name = f"xlsx_{table_name}"

                clean_cols = []
                seen_cols = set()
                for idx, h in enumerate(headers):
                    cleaned = re.sub(r"\W+", "_", h.strip()).strip("_").lower()
                    col_name = cleaned if cleaned else f"col_{idx+1}"
                    if col_name in seen_cols:
                        col_name = f"{col_name}_{idx+1}"
                    seen_cols.add(col_name)
                    clean_cols.append(col_name)

                cursor.execute(f'DROP TABLE IF EXISTS "{table_name}";')
                cols_def = ", ".join(f'"{c}" TEXT' for c in clean_cols)
                cursor.execute(f'CREATE TABLE "{table_name}" ({cols_def});')

                placeholders = ", ".join("?" for _ in clean_cols)
                insert_sql = f'INSERT INTO "{table_name}" VALUES ({placeholders});'
                for r in rows[1:]:
                    padded = r + [""] * max(0, len(clean_cols) - len(r))
                    cursor.execute(insert_sql, padded[:len(clean_cols)])

                created_tables.append(table_name)

            self.conn.commit()
            if created_tables:
                logger.info(f"Saved Excel (.xlsx) tables {created_tables} into local SQLite database.")
        except Exception as e:
            logger.warning(f"Failed to sync Excel (.xlsx) tables into SQLite: {e}")
        return created_tables

    def get_database_schema(self) -> str:
        """Read available SQLite tables and columns (excluding internal chat history tables)."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name NOT IN ('threads', 'messages');"
        )
        tables = [row["name"] for row in cursor.fetchall()]

        schema_lines = []
        for tbl in tables:
            cursor.execute(f"PRAGMA table_info('{tbl}');")
            # Hide large JSON/vector columns from prompt so the LLM writes clean SQL
            cols = [
                f"{c['name']} ({c['type']})"
                for c in cursor.fetchall()
                if c["name"] not in ("embedding_json", "metadata_json", "content")
            ]
            schema_lines.append(f"Table '{tbl}': {', '.join(cols)}")

        return "\n".join(schema_lines)

    def validate_sql(self, sql: str) -> Tuple[bool, str]:
        """Make sure the LLM only runs read-only SELECT queries."""
        cleaned = sql.strip().strip(";").strip()
        cleaned_lower = cleaned.lower()

        if not (cleaned_lower.startswith("select") or cleaned_lower.startswith("with")):
            return False, "Query must start with SELECT or WITH (read-only queries only)."

        for pattern in FORBIDDEN_SQL_PATTERNS:
            if re.search(pattern, cleaned_lower):
                return False, f"Forbidden SQL keyword detected: '{pattern}'."

        return True, ""

    async def generate_sql(self, query: str) -> Optional[str]:
        """Ask local Ollama LLM to translate the user's question into a SQLite SELECT query."""
        schema_desc = self.get_database_schema()
        if not schema_desc.strip():
            return None

        prompt = f"""You are a SQLite database assistant. Write a single safe SQL SELECT query to answer the user's question.
AVAILABLE TABLES AND COLUMNS:
{schema_desc}

USER QUESTION: "{query}"

RULES:
1. Return ONLY the raw SQL query with NO markdown fences, NO comments, and NO extra text.
2. Only SELECT queries are allowed.
3. CRITICAL: The `documents` table ALREADY has `filename`, `title`, `doc_type`, `chunk_count`, and `file_size`. Do NOT use JOIN with `document_chunks` to get `chunk_count`! Simply query:
   SELECT filename, title, doc_type, chunk_count, file_size FROM documents ORDER BY chunk_count DESC
4. If you ever join tables, ALWAYS prefix column names with the table name (e.g., `documents.doc_type`).

SQL:"""

        try:
            res = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=250,
            )
            raw_sql = res.choices[0].message.content or ""
            cleaned_sql = raw_sql.strip()
            if cleaned_sql.startswith("```sql"):
                cleaned_sql = cleaned_sql[6:]
            if cleaned_sql.startswith("```"):
                cleaned_sql = cleaned_sql[3:]
            if cleaned_sql.endswith("```"):
                cleaned_sql = cleaned_sql[:-3]
            return cleaned_sql.strip().rstrip(";")
        except Exception as e:
            logger.error(f"Text-to-SQL generation failed: {e}")
            return None

    def execute_sql(self, sql: str) -> Dict[str, Any]:
        """Run the validated SQL query on local SQLite and format the output as a Markdown table."""
        is_safe, error_msg = self.validate_sql(sql)
        if not is_safe:
            return {
                "success": False,
                "error": error_msg,
                "sql": sql,
                "columns": [],
                "rows": [],
                "markdown_table": "",
            }

        cursor = self.conn.cursor()
        try:
            cursor.execute(sql)
        except Exception as first_err:
            logger.warning(f"Primary SQL failed ('{sql}'): {first_err}. Retrying with clean documents inventory query.")
            sql = "SELECT filename, title, doc_type, chunk_count, file_size FROM documents ORDER BY chunk_count DESC"
            try:
                cursor.execute(sql)
            except Exception as e:
                logger.error(f"Fallback SQL execution error: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "sql": sql,
                    "columns": [],
                    "rows": [],
                    "markdown_table": "",
                }

        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description] if cursor.description else []
        data = [list(row) for row in rows]

        cursor.execute("SELECT COUNT(*) as total_docs, COALESCE(SUM(chunk_count), 0) as total_chunks FROM documents;")
        summary_row = cursor.fetchone()
        summary_line = ""
        if summary_row:
            summary_line = f"\n\n**Total Dokumen Tersimpan:** {summary_row['total_docs']} dokumen | **Total Chunks Terindeks:** {summary_row['total_chunks']} chunks"

        if columns and data:
            header = "| " + " | ".join(str(c) for c in columns) + " |"
            sep = "| " + " | ".join("---" for _ in columns) + " |"
            row_lines = ["| " + " | ".join(str(val) for val in r) + " |" for r in data[:20]]
            md_table = "\n".join([header, sep] + row_lines) + summary_line
        elif columns and not data:
            md_table = "*(Query returned 0 rows)*" + summary_line
        else:
            md_table = "*(No output)*" + summary_line

        return {
            "success": True,
            "sql": sql,
            "columns": columns,
            "rows": data,
            "row_count": len(data),
            "markdown_table": md_table,
        }

    async def run_text_to_sql(self, query: str) -> Optional[Dict[str, Any]]:
        """Generate, validate, and run a SQL query from natural language."""
        sql = await self.generate_sql(query)
        if not sql:
            return None
        return self.execute_sql(sql)


text_to_sql_service = TextToSQLService()
