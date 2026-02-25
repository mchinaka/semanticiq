# services/spreadsheet_parser.py
import csv
import io

def build_model_from_spreadsheet(file) -> dict:
    """
    MVP: Expect CSV with columns:
    Entity, Attribute, Type
    """
    decoded = file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(decoded))

    entities = {}

    for row in reader:
        ent = row["Entity"].strip()
        attr = row["Attribute"].strip()
        typ = row.get("Type", "string").strip()

        if ent not in entities:
            entities[ent] = {
                "id": ent,
                "label": ent,
                "attributes": [],
                "relationships": []
            }

        entities[ent]["attributes"].append({
            "id": attr,
            "type": typ
        })

    return {"entities": list(entities.values())}