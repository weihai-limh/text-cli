const cloud = require('wx-server-sdk');
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });

const INSTRUCTIONS = {
  'get_public_ip': require('./instructions/get_public_ip'),
  'xor_encrypt': require('./instructions/xor_encrypt'),
  'xor_decrypt': require('./instructions/xor_decrypt'),
};

exports.main = async (event, context) => {
  if (!event.httpMethod) {
    if (event.action === 'get_schema') {
      const schema = require('./schema.json');
      return { schema: schema };
    }
    const prompt = event.prompt;
    if (!prompt) {
      return {
        rst_types: 'text',
        rst_data: {
          text: JSON.stringify({
            status: 'error',
            result: 'MISSING_PROMPT: prompt is required for SDK call'
          })
        }
      };
    }
    return await executeInstruction(prompt, event);
  }
  
  const path = event.path || '';
  
  if (event.httpMethod === 'GET' && path === '/health') {
    return {
      status: 'ok',
      service: 'web-utils',
      version: '0.1.1'
    };
  }
  
  if (event.httpMethod === 'POST' && path === '/cli/text_cli') {
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
    
    return await executeInstruction(prompt, event);
  }
  
  return {
    rst_types: 'text',
    rst_data: {
      text: JSON.stringify({
        status: 'error',
        result: `UNKNOWN_PATH: ${event.httpMethod} ${path}`
      })
    }
  };
};

async function executeInstruction(prompt, event) {
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
  
  const firstComma = actionAndParams.indexOf(',');
  let action, paramsStr;
  if (firstComma === -1) {
    action = actionAndParams;
    paramsStr = '';
  } else {
    action = actionAndParams.substring(0, firstComma);
    paramsStr = actionAndParams.substring(firstComma + 1);
  }
  action = action.trim();
  
  const params = paramsStr ? paramsStr.split(',') : [];
  
  const handler = INSTRUCTIONS[action];
  if (!handler) {
    return {
      rst_types: 'text',
      rst_data: {
        text: JSON.stringify({
          status: 'error',
          result: `ACTION_NOT_FOUND: ${action}`
        })
      }
    };
  }
  
  try {
    return await handler.handler(params, event);
  } catch (error) {
    return {
      rst_types: 'text',
      rst_data: {
        text: JSON.stringify({
          status: 'error',
          result: `EXECUTION_ERROR: ${error.message}`
        })
      }
    };
  }
}
