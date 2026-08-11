/**
 * p_text-cli.md Guard — 防篡改验证
 *
 * 每次铸造前校验：
 *   1. 从 ledger-copy 分支读取 p_text-cli_copy.md（上次铸造时的快照）
 *   2. 验证当前 p_text-cli.md 是副本的纯追加（副本是当前文件的前缀）
 *   3. 通过 → 继续铸造 + 更新副本
 *   4. 失败 → 跳过铸造 + 告警
 *
 * 损失上限：1 天 TCC。副本只在上次成功铸造时更新。
 */

import { getFileContent, createOrUpdateFile, getFileInfo } from './github.js';

const COPY_BRANCH = 'ledger-copy';
const COPY_FILE = '.agents/p_text-cli_copy.md';

/**
 * 验证 newContent 是 copyContent 的纯追加。
 * 即 copyContent 是 newContent 的前缀。
 */
export function isPureAppend(copyContent, newContent) {
  if (!copyContent) {
    // 首次运行，副本不存在 → 视为通过
    return { ok: true, reason: 'first_run' };
  }

  if (newContent.startsWith(copyContent)) {
    return { ok: true, reason: 'append_verified' };
  }

  // 找到第一个差异位置
  const minLen = Math.min(copyContent.length, newContent.length);
  let diffPos = 0;
  while (diffPos < minLen && copyContent[diffPos] === newContent[diffPos]) {
    diffPos++;
  }

  const contextStart = Math.max(0, diffPos - 80);
  const contextEnd = Math.min(Math.max(copyContent.length, newContent.length), diffPos + 80);

  return {
    ok: false,
    reason: 'tamper_detected',
    diff_position: diffPos,
    copy_snippet: copyContent.slice(contextStart, contextEnd),
    new_snippet: newContent.slice(contextStart, contextEnd),
    copy_total_bytes: copyContent.length,
    new_total_bytes: newContent.length,
  };
}

/**
 * 从 ledger-copy 分支获取副本内容
 */
export async function getCopyContent(owner, repo, env) {
  try {
    const content = await getFileContent(owner, repo, COPY_FILE, COPY_BRANCH, env);
    if (!content) {
      return { ok: true, content: '', reason: 'copy_not_found' };
    }
    return { ok: true, content, reason: 'copy_loaded' };
  } catch (err) {
    // 分支或文件不存在 → 首次运行
    return { ok: true, content: '', reason: 'copy_branch_missing' };
  }
}

/**
 * 铸造成功后，更新 ledger-copy 分支的副本
 */
export async function updateCopy(owner, repo, newContent, env) {
  try {
    // 获取当前副本的 sha（如果存在）
    let sha = null;
    try {
      const info = await getFileInfo(owner, repo, COPY_FILE, COPY_BRANCH, env);
      if (info) sha = info.sha;
    } catch (_) {
      // 文件不存在 → sha 为 null，createOrUpdateFile 会创建
    }

    await createOrUpdateFile(
      owner, repo, COPY_FILE,
      newContent,
      'guard: 更新 p_text-cli 副本（铸造成功）',
      COPY_BRANCH,
      sha,
      env,
    );

    return { ok: true };
  } catch (err) {
    // 副本更新失败不影响主流程（下次铸造会用旧副本校验）
    return { ok: false, error: err.message };
  }
}
