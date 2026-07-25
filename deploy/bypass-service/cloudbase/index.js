const cloud = require('wx-server-sdk');
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });

const { routeTable, packages } = require('./config');

exports.main = async (event, context) => {
  // 1. 判断 HTTP 方法
  if (event.httpMethod === 'GET') {
    return handleGet(event);
  }
  
  if (event.httpMethod === 'POST') {
    return handlePost(event);
  }
  
  // 未知方法
  return {
    rst_types: 'text',
    rst_data: {
      text: JSON.stringify({
        status: 'error',
        result: `UNKNOWN_METHOD: ${event.httpMethod}`
      })
    }
  };
};

function handleGet(event) {
  const path = event.path || '';
  
  // GET /health → 返回健康检查
  if (path === '/health') {
    return {
      status: 'ok',
      service: 'text-cli-router',
      version: '1.0.0'
    };
  }
  
  // GET /text-cli/skills → 返回 {} (目前不对外暴露)
  if (path === '/text-cli/skills') {
    return {};
  }
  
  // 未知路径
  return {
    rst_types: 'text',
    rst_data: {
      text: JSON.stringify({
        status: 'error',
        result: `UNKNOWN_PATH: GET ${path}`
      })
    }
  };
}

async function handlePost(event) {
  const path = event.path || '';
  
  // POST /text_cli → 执行指令路由
  if (path === '/cli') {
    let body;
    try {
      body = typeof event.body === 'string' ? JSON.parse(event.body) : event.body;
    } catch (e) {
      return {
        rst_types: 'text',
        rst_data: {
          text: JSON.stringify({
            status: 'error',
            result: 'INVALID_BODY: event.body is not valid JSON'
          })
        }
      };
    }
    
    const prompt = body.prompt;
    if (!prompt) {
      return {
        rst_types: 'text',
        rst_data: {
          text: JSON.stringify({
            status: 'error',
            result: 'MISSING_PROMPT: prompt is required'
          })
        }
      };
    }
    
    // 检查是否是 AI:text-cli;query
    if (prompt.startsWith('AI:text-cli;query')) {
      return await handleQuery(prompt);
    }
    
    // 执行指令路由
    return await routeInstruction(prompt, event);
  }
  
  // 未知路径
  return {
    rst_types: 'text',
    rst_data: {
      text: JSON.stringify({
        status: 'error',
        result: `UNKNOWN_PATH: POST ${path}`
      })
    }
  };
}

async function handleQuery(prompt) {
  // 解析模式: AI:text-cli;query 或 AI:text-cli;query,json
  const params = prompt.substring('AI:text-cli;query'.length).trim();
  const mode = params ? params.split(',')[0].trim() : 'text';
  
  // 1. 并发获取所有包的 schema (通过 SDK 调用)
  const schemaPromises = packages.map(pkg => 
    cloud.callFunction({
      name: pkg,
      data: { action: 'get_schema' }
    }).catch(err => ({ error: err.message, pkg }))
  );
  const schemaResults = await Promise.all(schemaPromises);
  
  // 2. 提取 schema
  const schemas = [];
  for (const result of schemaResults) {
    if (result.error) {
      console.error(`Failed to get schema from ${result.pkg}:`, result.error);
      continue;
    }
    if (result.result && result.result.schema) {
      schemas.push(result.result.schema);
    }
  }
  
  // 3. 扁平化指令列表
  const directives = flattenSchemas(schemas);
  
  // 4. 渲染输出
  if (mode === 'json') {
    return {
      rst_types: 'text',
      rst_data: {
        text: JSON.stringify({
          status: 'ok',
          result: JSON.stringify({ directives })
        })
      }
    };
  }
  if (mode === 'compact') {
    const lines = directives.map(d => `${d.domain};${d.action}`);
    return {
      rst_types: 'text',
      rst_data: {
        text: JSON.stringify({
          status: 'ok',
          result: lines.join('\n')
        })
      }
    };
  }
  // 默认 text 模式
  const text = renderText(directives);
  return {
    rst_types: 'text',
    rst_data: {
      text: JSON.stringify({
        status: 'ok',
        result: text
      })
    }
  };
}

function flattenSchemas(schemas) {
  const directives = [];
  for (const schema of schemas) {
    for (const directive of schema.directives) {
      directives.push({
        ...directive,
        _package: schema.id
      });
    }
  }
  return directives;
}

function renderText(directives) {
  let text = 'Available directives:\n\n';
  for (const d of directives) {
    text += `  ${d.domain};${d.action}\n`;
    text += `    ${d.description}\n`;
    if (d.params && d.params.length > 0) {
      text += `    params: ${d.params.map(p => p.name + (p.required ? '*' : '')).join(', ')}\n`;
    }
    text += '\n';
  }
  return text;
}

async function routeInstruction(prompt, event) {
  // 解析 prompt: AI:web-utils;get_public_ip
  const match = prompt.match(/^AI:\s*([^;]+);\s*([^(]+)(?:\(.*\))?$/);
  if (!match) {
    return {
      rst_types: 'text',
      rst_data: {
        text: JSON.stringify({
          status: 'error',
          result: `INVALID_PROMPT: ${prompt}`
        })
      }
    };
  }
  
  const domain = match[1].trim();
  const actionAndParams = match[2].trim();
  
  // 查路由表
  const functionName = routeTable[domain];
  if (!functionName) {
    return {
      rst_types: 'text',
      rst_data: {
        text: JSON.stringify({
          status: 'error',
          result: `DOMAIN_NOT_FOUND: ${domain}`
        })
      }
    };
  }
  
  // 调用指令云函数
  try {
    const result = await cloud.callFunction({
      name: functionName,
      data: {
        prompt: prompt,
        _routerEvent: event  // 把原始event传过去，指令云函数用event._routerEvent拿原始请求信息
      }
    });
    
    // result.result 是指令云函数返回的结果
    // 格式应为: {rst_types: "text", rst_data: {text: "{\"status\":\"ok\",\"result\":\"...\"}"}}
    return result.result;
  } catch (error) {
    return {
      rst_types: 'text',
      rst_data: {
        text: JSON.stringify({
          status: 'error',
          result: `FUNCTION_CALL_FAILED: ${error.message}`
        })
      }
    };
  }
}
