# OpenAPI & JSON Schema Contract Intelligence

API Detective supports **OpenAPI 3.0**, **OpenAPI 3.1**, **Swagger 2.0** (JSON and YAML), and standalone **JSON Schema** documents.

## Supported Validations

1. **Required Properties (`SCH-001`)**: Verifies all fields listed in `required: [...]` exist and are non-null at every nested object level.
2. **Unexpected Properties (`SCH-002`)**: Flags extra fields when `additionalProperties: false` is declared on the schema object.
3. **Strict Type Checking (`SCH-003`)**: Validates `string`, `integer`, `number`, `boolean`, `object`, `array`, and `null` (including `nullable: true` and union type arrays in OpenAPI 3.1).
4. **Enum Validation (`SCH-004`)**: Confirms field values match the documented `enum` list.
5. **Request & Response Contract Matching (`SCH-005`)**: Resolves local `$ref` pointers (`#/components/schemas/...` and `#/definitions/...`), matches URL paths against parameterized templates (`/users/{id}`), and validates both request bodies and status-keyed response payloads.
6. **Frontend/Backend Casing Mismatch (`INT-006`)**: Detects when a client sends `camelCase` keys (`customerId`) to an endpoint whose OpenAPI schema requires `snake_case` (`customer_id`).
