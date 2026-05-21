def ok(text: str) -> dict:
    return {"rst_types": "text", "rst_data": {"text": text}}


def error(text: str) -> dict:
    return {"rst_types": "text", "rst_data": {"text": f"Directive execution failed: {text}"}}
