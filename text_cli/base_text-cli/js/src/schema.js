import staticSchema from '../schema/text_cli_schema.json';

export async function getSchema(db) {
  if (db) {
    const rows = await db
      .prepare(
        `SELECT id, name, category, description, domain, action,
                parameters_json, prompt_template, trigger_keywords_json,
                response_type, response_example_json
         FROM directives WHERE enabled = 1`
      )
      .all();

    const schema = {};
    for (const row of rows.results) {
      schema[row.id] = {
        id: row.id,
        name: row.name,
        category: row.category,
        description: row.description,
        directive: `指令:${row.domain};${row.action}`,
        parameters: JSON.parse(row.parameters_json || '[]'),
        prompt_template: row.prompt_template,
        trigger_keywords: JSON.parse(row.trigger_keywords_json || '[]'),
        response_type: row.response_type,
        response_example: row.response_example_json
          ? JSON.parse(row.response_example_json)
          : undefined,
      };
    }

    if (Object.keys(schema).length > 0) {
      return schema;
    }
  }

  return staticSchema;
}
