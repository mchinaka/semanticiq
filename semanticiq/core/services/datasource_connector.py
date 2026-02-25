import csv
import io

def build_model_from_data_source(source_type: str, config: dict) -> dict:
    """
    MVP: Only CSV supported.
    Future: DB, API, JSON, Parquet, etc.
    """
    if source_type == "csv":
        return build_from_csv(config)
    else:
        raise ValueError(f"Unsupported sourceType: {source_type}")


def build_from_csv(config: dict) -> dict:
    """
    Expect config["csvData"] to contain raw CSV text.
    """
    csv_text = config.get("csvData")
    if not csv_text:
        raise ValueError("csvData missing")

    reader = csv.DictReader(io.StringIO(csv_text))
    fields = reader.fieldnames or []

    return {
        "entities": [
            {
                "id": "Record",
                "label": "Record",
                "attributes": [{"id": f, "type": "string"} for f in fields],
                "relationships": []
            }
        ],
        "source": {"type": "csv"}
    }
