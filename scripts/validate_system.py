"""Validate system.yaml against the provided schema and its referenced OpenAPI routes."""

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


def main():
    root = Path(__file__).resolve().parents[1]
    document = yaml.safe_load((root / "system.yaml").read_text(encoding="utf-8"))
    schema = json.loads((root / "system.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(document), key=lambda error: error.json_path)
    if errors:
        raise SystemExit("\n".join(f"{error.json_path}: {error.message}" for error in errors))

    services = document["services"]
    for name, service in services.items():
        spec = yaml.safe_load((root / service["openapi"]).read_text(encoding="utf-8"))
        if "get" not in spec["paths"].get(service.get("health", "/health"), {}):
            raise SystemExit(f"{name}: health endpoint is missing from OpenAPI")
        if not (root / service["migrations"]).is_dir():
            raise SystemExit(f"{name}: migration directory is missing")
        for call in service.get("calls", []):
            if call["url_env"] not in service["env"]:
                raise SystemExit(f"{name}: {call['url_env']} is missing from env")
            peer = services[call["service"]]
            paths = yaml.safe_load((root / peer["openapi"]).read_text(encoding="utf-8"))["paths"]
            for endpoint in call["endpoints"]:
                method, path = endpoint.split(" ", 1)
                if method.lower() not in paths.get(path, {}):
                    raise SystemExit(f"{name}: {endpoint} is missing from {call['service']} OpenAPI")
    print("system.yaml matches the professor's schema and the referenced OpenAPI routes.")


if __name__ == "__main__":
    main()
