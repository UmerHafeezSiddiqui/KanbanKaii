"""Task-batch wire schema shared by AI providers."""

TASK_BATCH_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "isActionableTask": {"type": "boolean"},
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "priority": {
                        "type": "string",
                        "enum": ["HIGH", "MEDIUM", "LOW"],
                    },
                },
                "required": ["title", "description", "priority"],
            },
        },
    },
    "required": ["isActionableTask", "tasks"],
}
