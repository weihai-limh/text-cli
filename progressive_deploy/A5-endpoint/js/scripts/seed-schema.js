import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const schemaPath = resolve(__dirname, '../src/config/schema.json');

const schema = JSON.parse(readFileSync(schemaPath, 'utf-8'));
const directives = Object.entries(schema).filter(([key]) => !key.startsWith('_'));

console.log(`Found ${directives.length} directives in ${schemaPath}`);

console.log('\nTo import into D1, run the following commands:\n');

for (const [id, entry] of directives) {
  const paramsJson = JSON.stringify(entry.parameters || []);
  const keywordsJson = JSON.stringify(entry.trigger_keywords || []);
  const exampleJson = entry.response_example ? JSON.stringify(entry.response_example) : 'null';
  const directiveKey = entry.directive || `指令:${entry.category};${entry.name}`;

  const sql = `INSERT OR IGNORE INTO directives (id, name, category, description, domain, action, backend_url, parameters_json, prompt_template, trigger_keywords_json, response_type, response_example_json, directive_key) VALUES ('${id}', '${entry.name || ''}', '${entry.category || ''}', '${(entry.description || '').replace(/'/g, "''")}', '${entry.category || ''}', '${entry.name || ''}', '${entry.url || ''}', '${paramsJson.replace(/'/g, "''")}', '${(entry.prompt_template || '').replace(/'/g, "''")}', '${keywordsJson}', '${entry.response_type || 'text'}', '${exampleJson.replace(/'/g, "''")}', '${directiveKey.replace(/'/g, "''")}');`;

  console.log(`wrangler d1 execute text-cli-endpoint-db --command="${sql.replace(/"/g, '\\"')}"`);
}

console.log('\nOr copy the SQL commands and execute them manually in the Cloudflare dashboard.');
