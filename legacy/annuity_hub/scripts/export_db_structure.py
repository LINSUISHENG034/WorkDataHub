import json
import logging
from typing import Dict, List
from database_operations.mysql_ops import MySqlDBManager
from sqlalchemy import inspect

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("export_db_structure.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class DatabaseExporter:
    def __init__(self):
        try:
            self.db_manager = MySqlDBManager(database=None)
            logger.info("Successfully initialized database connection")
        except Exception as e:
            logger.error(f"Failed to initialize database connection: {str(e)}")
            raise

    def get_all_databases(self) -> List[str]:
        """Get list of all databases"""
        try:
            self.db_manager.cursor.execute("SHOW DATABASES")
            databases = [
                db[0]
                for db in self.db_manager.cursor.fetchall()
                if db[0]
                not in ("information_schema", "mysql", "performance_schema", "sys")
            ]
            logger.info(f"Found {len(databases)} databases")
            return databases
        except Exception as e:
            logger.error(f"Error getting databases: {str(e)}")
            raise

    def get_table_structure(self, database: str) -> Dict:
        """Get structure of all tables in a database"""
        try:
            logger.info(f"Getting structure for database: {database}")
            self.db_manager.switch_database(database)
            inspector = inspect(self.db_manager.engine)

            structure = {}
            for table_name in inspector.get_table_names():
                logger.info(f"Processing table: {table_name}")
                table_info = {"columns": [], "indexes": [], "foreign_keys": []}

                # Get columns
                for column in inspector.get_columns(table_name):
                    table_info["columns"].append(
                        {
                            "name": column["name"],
                            "type": str(column["type"]),
                            "nullable": column["nullable"],
                            "default": column["default"],
                            "primary_key": column.get("primary_key", False),
                        }
                    )

                # Get indexes
                for index in inspector.get_indexes(table_name):
                    table_info["indexes"].append(
                        {
                            "name": index["name"],
                            "columns": index["column_names"],
                            "unique": index["unique"],
                        }
                    )

                # Get foreign keys
                for fk in inspector.get_foreign_keys(table_name):
                    table_info["foreign_keys"].append(
                        {
                            "name": fk["name"],
                            "constrained_columns": fk["constrained_columns"],
                            "referred_table": fk["referred_table"],
                            "referred_columns": fk["referred_columns"],
                        }
                    )

                structure[table_name] = table_info

            return structure
        except Exception as e:
            logger.error(f"Error getting table structure for {database}: {str(e)}")
            raise

    def export_to_file(self, output_file: str = "db_structure.json"):
        """Export database structure to JSON file"""
        try:
            result = {}

            databases = self.get_all_databases()
            for db in databases:
                try:
                    result[db] = self.get_table_structure(db)
                except Exception as e:
                    logger.error(f"Skipping database {db} due to error: {str(e)}")
                    continue

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            logger.info(f"Successfully exported database structure to {output_file}")
        except Exception as e:
            logger.error(f"Error exporting database structure: {str(e)}")
            raise


if __name__ == "__main__":
    try:
        exporter = DatabaseExporter()
        exporter.export_to_file()
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
