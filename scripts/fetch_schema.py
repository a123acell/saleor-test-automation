# -*- coding: utf-8 -*-
"""拉取 Saleor GraphQL schema（内省查询），输出原始 JSON 与 SDL。

一次性脚本：依赖本地 Saleor 已启动（http://localhost:8000/graphql/）。
"""
import json
import os
import sys

import requests

ENDPOINT = os.environ.get("SALEOR_GRAPHQL_URL", "http://localhost:8000/graphql/")
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schema")

INTROSPECTION_QUERY = """
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    subscriptionType { name }
    types {
      ...FullType
    }
    directives {
      name
      description
      locations
      args { ...InputValue }
    }
  }
}

fragment FullType on __Type {
  kind
  name
  description
  fields(includeDeprecated: true) {
    name
    description
    args { ...InputValue }
    type { ...TypeRef }
    isDeprecated
    deprecationReason
  }
  inputFields { ...InputValue }
  interfaces { ...TypeRef }
  enumValues(includeDeprecated: true) {
    name
    description
    isDeprecated
    deprecationReason
  }
  possibleTypes { ...TypeRef }
}

fragment InputValue on __InputValue {
  name
  description
  type { ...TypeRef }
  defaultValue
}

fragment TypeRef on __Type {
  kind
  name
  ofType {
    kind
    name
    ofType {
      kind
      name
      ofType {
        kind
        name
        ofType {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
              }
            }
          }
        }
      }
    }
  }
}
"""


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)

    resp = requests.post(
        ENDPOINT,
        json={"query": INTROSPECTION_QUERY, "operationName": "IntrospectionQuery"},
        timeout=60,
    )
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("errors"):
        print("内省失败：", json.dumps(payload["errors"], ensure_ascii=False)[:500])
        return 1

    raw_path = os.path.join(OUT_DIR, "saleor_schema.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    schema = payload["data"]["__schema"]
    types = [t for t in schema["types"] if not t["name"].startswith("__")]

    query_type = schema["queryType"]["name"] if schema.get("queryType") else None
    mutation_type = schema["mutationType"]["name"] if schema.get("mutationType") else None

    query_fields = next((t["fields"] for t in types if t["name"] == query_type), []) or []
    mutation_fields = next((t["fields"] for t in types if t["name"] == mutation_type), []) or []

    stats = {
        "endpoint": ENDPOINT,
        "query_type": query_type,
        "mutation_type": mutation_type,
        "query_field_count": len(query_fields),
        "mutation_field_count": len(mutation_fields),
        "type_count": len(types),
        "object_types": len([t for t in types if t["kind"] == "OBJECT"]),
        "enum_types": len([t for t in types if t["kind"] == "ENUM"]),
        "input_types": len([t for t in types if t["kind"] == "INPUT_OBJECT"]),
        "scalar_types": len([t for t in types if t["kind"] == "SCALAR"]),
    }
    with open(os.path.join(OUT_DIR, "schema_stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    # 尝试生成 SDL（有 graphql-core 时）
    try:
        from graphql import build_client_schema, print_schema

        client_schema = build_client_schema(payload["data"])
        sdl = print_schema(client_schema)
        with open(os.path.join(OUT_DIR, "saleor_schema.graphql"), "w", encoding="utf-8") as f:
            f.write(sdl)
        stats["sdl_generated"] = True
        stats["sdl_chars"] = len(sdl)
    except ImportError:
        stats["sdl_generated"] = False

    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())