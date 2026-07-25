exports.handler = async (params) => {
  // params: [plaintext, key]
  const [plaintext, key] = params;
  
  if (!plaintext || !key) {
    return {
      rst_types: 'text',
      rst_data: {
        text: JSON.stringify({
          status: 'error',
          result: 'MISSING_PARAM: plaintext and key are required'
        })
      }
    };
  }
  
  // XOR加密
  const plaintextBytes = Buffer.from(plaintext, 'utf8');
  const keyBytes = Buffer.from(key, 'utf8');
  const ciphertextBytes = xorBytes(plaintextBytes, keyBytes);
  
  return {
    rst_types: 'text',
    rst_data: {
      text: JSON.stringify({
        status: 'ok',
        result: ciphertextBytes.toString('hex')
      })
    }
  };
};

function xorBytes(data, key) {
  const result = Buffer.alloc(data.length);
  for (let i = 0; i < data.length; i++) {
    result[i] = data[i] ^ key[i % key.length];
  }
  return result;
}
