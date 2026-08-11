// 现代协议信封构造辅助 (SPEC §1.2.2)
// rst_data 直接承载业务 dict；rst_err 为空=成功，非空=错误码。
// handler 只负责业务结果，由本模块统一裹成协议信封，避免各处重复构造。

function ok(data) {
  return { rst_types: 'text', rst_data: data, rst_err: '' };
}

function err(code, reason) {
  return { rst_types: 'text', rst_data: { status: 'error', reason }, rst_err: code };
}

module.exports = { ok, err };
