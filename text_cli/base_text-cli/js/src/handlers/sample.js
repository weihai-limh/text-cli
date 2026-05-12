import { registerHandler } from '../registry.js';

registerHandler('示例领域', '回显', (params) => {
  return params.length > 0
    ? `回显结果: ${params.join(', ')}`
    : '回显结果: (无参数)';
});

registerHandler('示例领域', '问候', (params) => {
  const name = params[0] || '世界';
  return `你好, ${name}!`;
});

registerHandler('示例领域', '列表', () => {
  return '示例指令列表:\n- 回显: 回显参数\n- 问候: 问候指定名称\n- 列表: 显示此列表';
});
