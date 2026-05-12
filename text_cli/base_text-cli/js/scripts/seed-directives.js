import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const schemaPath = resolve(__dirname, '..', 'schema', 'text_cli_schema.json');
const schema = JSON.parse(readFileSync(schemaPath, 'utf-8'));

const rows = Object.values(schema).map(entry => {
  const domain = entry.directive.replace(/^指令[：:]/, '').split(';')[0];
  const action = entry.directive.split(';')[1] || '';
  const paramsJson = JSON.stringify(entry.parameters || []);
  const keywordsJson = JSON.stringify(entry.trigger_keywords || []);
  const exampleJson = entry.response_example ? JSON.stringify(entry.response_example) : null;

  return `('${entry.id}', '${domain}', '${action}', '${entry.name}', '${entry.category || ''}', '${(entry.description || '').replace(/'/g, "''")}', '${paramsJson}', '${entry.prompt_template || ''}', '${keywordsJson}', '${entry.response_type || 'text'}', ${exampleJson ? `'${exampleJson.replace(/'/g, "''")}'` : 'NULL'}, 'static', 1)`;
}).join(',\n  ');

const sql = `INSERT OR REPLACE INTO directives (id, domain, action, name, category, description, parameters_json, prompt_template, trigger_keywords_json, response_type, response_example_json, handler_type, enabled)
VALUES
  ${rows};`;

console.log('-- Generated SQL:');
console.log(sql);
console.log('\n-- Executing via wrangler...');

const tmpFile = resolve(__dirname, '..', '.tmp_seed.sql');
import { writeFileSync } from 'node:fs';
writeFileSync(tmpFile, sql, 'utf-8');

try {
  execSync(`wrangler d1 execute text-cli-db --file="${tmpFile}"`, { stdio: 'inherit' });
  console.log('✅ Schema seeded successfully');
} catch (e) {
  console.error('❌ Failed to seed schema:', e.message);
  process.exit(1);
} finally {
  import { unlinkSync } from 'node:fs';
  try { unlinkSync(tmpFile); } catch {}
}
