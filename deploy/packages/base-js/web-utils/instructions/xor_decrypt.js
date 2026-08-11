const { ok, err } = require('./envelope');

exports.handler = async (params) => {
  // params: [ciphertext, key]
  const [ciphertext, key] = params;

  if (!ciphertext || !key) {
    return err('MISSING_PARAM', 'ciphertext and key are required');
  }

  // 验证 ciphertext 是合法 hex
  if (!/^[0-9a-fA-F]+$/.test(ciphertext)) {
    return err('INVALID_HEX', 'ciphertext must be hex string');
  }

  // XOR 解密
  const ciphertextBytes = Buffer.from(ciphertext, 'hex');
  const keyBytes = Buffer.from(key, 'utf8');
  const plaintextBytes = xorBytes(ciphertextBytes, keyBytes);

  return ok({ status: 'ok', result: plaintextBytes.toString('utf8') });
};

function xorBytes(data, key) {
  const result = Buffer.alloc(data.length);
  for (let i = 0; i < data.length; i++) {
    result[i] = data[i] ^ key[i % key.length];
  }
  return result;
}
