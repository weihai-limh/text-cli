/**
 * TCC Mint Worker — Main Entry
 * ref: docs/Production_TCC_CN.md §3
 *
 * v3: 严格每日一次 UTC 0:00 Cron 触发。
 *     移除 webhook 事件驱动，不再响应 GitHub push 事件。
 *     铸造写入 TCC_ledger.md，lemondy 审批后合并生效。
 */

import { calculateMint } from './mint.js';
import { isProcessed, markProcessed, initIdempotencyTable } from './idempotent.js';
import {
  getFileContent,
  getFileInfo,
  getRecentCommits,
  findOrCreateIssue,
  postIssueComment,
  getRef,
  createBranch,
  createOrUpdateFile,
  createPR,
  findOpenPR,
  fromBase64,
} from './github.js';
import { formatLedgerRecord, formatPRBody, formatAlert, formatGuardAlert } from './format.js';
import { getCopyContent, isPureAppend, updateCopy } from './guard.js';

const ZERO_SHA = '0000000000000000000000000000000000000000';
const LEDGER_FILE = 'TCC_ledger.md';
const MAIN_BRANCH = 'main';

function parseRepo(env) {
  const [owner, repo] = (env.REPO || '').split('/');
  return { owner, repo };
}

async function getConfig(env) {
  return {
    scalingFactor: parseInt(env.SCALING_FACTOR, 10) || 100,
    dailyMintCap: parseInt(env.DAILY_MINT_CAP, 10) || 100,
    deltaBytesThreshold: parseInt(env.DELTA_BYTES_THRESHOLD, 10) || 10,
    rawScoreThreshold: parseInt(env.RAW_SCORE_THRESHOLD, 10) || 200,
    anchorFile: env.ANCHOR_FILE || '.agents/p_text-cli.md',
    ledgerFile: env.LEDGER_FILE || LEDGER_FILE,
  };
}

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

async function getOrCreateBranch(owner, repo, branchName, env) {
  const mainRef = await getRef(owner, repo, MAIN_BRANCH, env);
  const baseSha = mainRef.object.sha;

  const result = await createBranch(owner, repo, branchName, baseSha, env);

  if (result.existed) {
    const ref = await getRef(owner, repo, branchName, env);
    return { sha: ref.object.sha };
  }

  return { sha: baseSha };
}

function getCycleNumber(existingLedgerContent) {
  if (!existingLedgerContent || existingLedgerContent.trim() === '') return 1;

  const matches = existingLedgerContent.match(/## 周期 #(\d+)/g);
  if (!matches || matches.length === 0) return 1;

  const nums = matches.map(m => parseInt(m.match(/#(\d+)/)[1], 10));
  return Math.max(...nums) + 1;
}

async function computeAndCreatePR(owner, repo, beforeSha, afterSha, env, config) {
  const { anchorFile } = config;
  const date = todayStr();
  const branchName = `tcc-mint/${date}`;

  const oldContent = beforeSha === ZERO_SHA
    ? ''
    : await getFileContent(owner, repo, anchorFile, beforeSha, env);

  const newContent = await getFileContent(owner, repo, anchorFile, afterSha, env);

  // 🛡️ 防篡改检查：验证 p_text-cli.md 是纯追加
  const copyResult = await getCopyContent(owner, repo, env);
  const guardCheck = isPureAppend(copyResult.content, newContent);
  if (!guardCheck.ok) {
    const issueNumber = await findOrCreateIssue(owner, repo, 'TCC 每日铸造日志', env);
    await postIssueComment(owner, repo, issueNumber,
      formatGuardAlert(guardCheck, `${beforeSha.slice(0, 7)}..${afterSha.slice(0, 7)}`), env);
    return { type: 'guard_blocked', reason: guardCheck.reason };
  }

  const result = await calculateMint(oldContent, newContent, config);

  const commitRange = beforeSha === ZERO_SHA
    ? afterSha
    : `${beforeSha.slice(0, 7)}..${afterSha.slice(0, 7)}`;

  if (result.type === 'genesis' || beforeSha === ZERO_SHA) {
    const genesisPrTitle = `TCC 创世铸造 — ${date}`;

    // ★ Bug 修复：先检查创世是否已在账本中完成
    const existingLedgerInfo = await getFileInfo(owner, repo, LEDGER_FILE, MAIN_BRANCH, env);
    const existingLedgerContent = existingLedgerInfo
      ? fromBase64(existingLedgerInfo.content)
      : '';
    if (existingLedgerContent.includes('## 创世铸造')) {
      return { type: 'genesis', duplicate: true, reason: 'genesis_already_recorded' };
    }

    const existingGenesisPR = await findOpenPR(owner, repo, `weihai-limh:tcc-mint/${date}`, env);

    if (existingGenesisPR) {
      return { type: 'genesis', pr_url: existingGenesisPR.html_url, duplicate: true };
    }

    await getOrCreateBranch(owner, repo, branchName, env);

    const ledgerInfo = await getFileInfo(owner, repo, LEDGER_FILE, MAIN_BRANCH, env);
    const ledgerContent = ledgerInfo
      ? fromBase64(ledgerInfo.content)
      : '';
    const ledgerSha = ledgerInfo ? ledgerInfo.sha : null;

    const ledgerRecord = formatLedgerRecord({ type: 'genesis' }, 0, commitRange);

    await createOrUpdateFile(
      owner, repo, LEDGER_FILE,
      ledgerContent + ledgerRecord,
      `tcc-mint: 创世铸造 — ${date}`,
      branchName,
      ledgerSha,
      env,
    );

    const pr = await createPR(
      owner, repo,
      genesisPrTitle,
      branchName,
      MAIN_BRANCH,
      formatPRBody({ type: 'genesis' }, 0, commitRange),
      env,
    );

    return { type: 'genesis', pr_url: pr.html_url, pr_number: pr.number };
  }

  const existingPR = await findOpenPR(owner, repo, `weihai-limh:tcc-mint/${date}`, env);
  const prTitle = `TCC 每日铸造 — ${date}`;

  await getOrCreateBranch(owner, repo, branchName, env);

  const ledgerInfo = await getFileInfo(owner, repo, LEDGER_FILE, MAIN_BRANCH, env);
  const ledgerContent = ledgerInfo ? fromBase64(ledgerInfo.content) : '';
  const ledgerSha = ledgerInfo ? ledgerInfo.sha : null;
  const cycleNum = getCycleNumber(ledgerContent);

  const ledgerRecord = formatLedgerRecord(result, cycleNum, commitRange);

  await createOrUpdateFile(
    owner, repo, LEDGER_FILE,
    ledgerContent + ledgerRecord,
    `tcc-mint: 周期 #${cycleNum} — ${date}`,
    branchName,
    ledgerSha,
    env,
  );

  if (existingPR) {
    return {
      type: 'daily',
      cycle: cycleNum,
      mint_ceiling: result.mint_ceiling,
      pr_url: existingPR.html_url,
      updated: true,
    };
  }

  const pr = await createPR(
    owner, repo,
    prTitle,
    branchName,
    MAIN_BRANCH,
    formatPRBody(result, cycleNum, commitRange, result.old_hash, result.new_hash),
    env,
  );

  // 🛡️ 铸造成功 → 更新 ledger-copy 副本
  if (result.mint_ceiling > 0) {
    const updateResult = await updateCopy(owner, repo, newContent, env);
    if (!updateResult.ok) {
      console.warn('guard: 副本更新失败（下次铸造将使用旧副本校验）:', updateResult.error);
    }
  }

  return {
    type: 'daily',
    cycle: cycleNum,
    mint_ceiling: result.mint_ceiling,
    pr_url: pr.html_url,
    pr_number: pr.number,
  };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === '/api/health') {
      return Response.json({
        status: 'ok',
        trigger: 'scheduled',
        schedule: '0 0 * * *',
        description: '严格每日一次 UTC 0:00 Cron 触发。不再响应 webhook 推送事件。'
      });
    }

    return new Response('方法不允许。本 Worker 仅通过 Cron 定时触发，不接受外部请求。', {
      status: 405,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' }
    });
  },

  async scheduled(event, env) {
    const { owner, repo } = parseRepo(env);
    const config = await getConfig(env);

    try {
      const since = new Date(Date.now() - 24 * 60 * 60 * 1000);
      const commits = await getRecentCommits(owner, repo, config.anchorFile, since, env);

      if (commits.length === 0) {
        return;
      }

      const oldest = commits[commits.length - 1];
      const newest = commits[0];

      if (env.DB) {
        await initIdempotencyTable(env.DB);
        if (await isProcessed(env.DB, newest.sha)) {
          return;
        }
      }

      const beforeSha = oldest.parents?.[0]?.sha || ZERO_SHA;
      const afterSha = newest.sha;

      const result = await computeAndCreatePR(owner, repo, beforeSha, afterSha, env, config);

      if (env.DB) {
        await markProcessed(env.DB, afterSha);
      }

      console.log(JSON.stringify(result));
    } catch (err) {
      try {
        const issueNumber = await findOrCreateIssue(owner, repo, 'TCC 每日铸造日志', env);
        await postIssueComment(owner, repo, issueNumber, formatAlert('scheduled', err.message), env);
      } catch (_) {}
    }
  },
};
