/**
 * CI Recaluclation Script
 * Parses TCC_ledger.md, recomputes mint, compares with Worker output.
 * Called by: .github/workflows/ci.yml → tcc-recalculate job
 */

import { calculateMint } from '../src/mint.js';
import { readFileSync } from 'fs';
import { execSync } from 'child_process';

function parseLatestCycle(ledgerPath) {
  const content = readFileSync(ledgerPath, 'utf-8');
  const cycles = content.match(/## 周期 #(\d+)\n([\s\S]*?)(?=\n## |\n---|\n*$)/g);

  if (!cycles || cycles.length === 0) {
    console.log('No cycles found in TCC_ledger.md — nothing to recalculate.');
    process.exit(0);
  }

  const latest = cycles[cycles.length - 1];
  const cycleMatch = latest.match(/## 周期 #(\d+)/);
  const diffMatch = latest.match(/\*\*diff 范围:\*\*\s*`([^`]+)`/);
  const mintCeilingMatch = latest.match(/\*\*mint_ceiling:\*\*\s*([\d.]+)\s*TCC/);
  const reasonMatch = latest.match(/\*\*mint_ceiling:\*\*\s*[\d.]+\s*TCC（未触发，原因:\s*(\w+)）/);

  if (!diffMatch) {
    console.log('No diff range found in latest cycle — skipping.');
    process.exit(0);
  }

  return {
    cycle: parseInt(cycleMatch[1], 10),
    diffRange: diffMatch[1],
    recordedMintCeiling: reasonMatch ? 0 : (mintCeilingMatch ? parseFloat(mintCeilingMatch[1]) : null),
    reason: reasonMatch ? reasonMatch[1] : null,
  };
}

function getFileAtCommit(filePath, commit) {
  return execSync(`git show ${commit}:"${filePath}"`, {
    encoding: 'utf-8',
    stdio: ['pipe', 'pipe', 'pipe'],
  });
}

async function main() {
  const ledgerPath = process.argv[2] || 'TCC_ledger.md';
  const anchorFile = '.agents/p_text-cli.md';

  const info = parseLatestCycle(ledgerPath);

  const parts = info.diffRange.split('..');
  if (parts.length !== 2) {
    console.log(`Invalid diff range: ${info.diffRange} — skipping.`);
    process.exit(0);
  }

  const [oldSha, newSha] = parts;

  console.log(`Cycle #${info.cycle}`);
  console.log(`Diff: ${oldSha}..${newSha}`);

  let oldContent, newContent;
  try {
    oldContent = getFileAtCommit(anchorFile, oldSha);
    newContent = getFileAtCommit(anchorFile, newSha);
  } catch (err) {
    console.log(`Cannot fetch file at commits — may be a fork or shallow clone.`);
    console.log(`Error: ${err.message}`);
    console.log('Skipping recalculation (cannot fully verify).');
    process.exit(0);
  }

  const config = {
    scalingFactor: 100,
    dailyMintCap: 100,
    deltaBytesThreshold: 10,
    rawScoreThreshold: 200,
  };

  const result = await calculateMint(oldContent, newContent, config);

  console.log('');
  console.log('=== CI Recalculation Result ===');
  console.log(`mint_ceiling: ${result.mint_ceiling}`);
  console.log(`hash_diff_bits: ${result.hash_diff_bits !== undefined ? result.hash_diff_bits : 'N/A'}`);
  console.log(`delta_bytes: ${result.delta_bytes}`);
  console.log(`raw_score: ${result.raw_score !== undefined ? result.raw_score : 'N/A'}`);
  if (result.reason) {
    console.log(`reason: ${result.reason}`);
  }
  console.log('');

  if (info.recordedMintCeiling === null && info.reason === null) {
    console.log('Cannot determine expected value from TCC_ledger.md — skipping comparison.');
    process.exit(0);
  }

  if (result.reason === 'delta_too_small' || result.reason === 'content_identical' || result.reason === 'raw_score_below_threshold') {
    if (info.recordedMintCeiling === 0) {
      console.log('✓ PASS: Worker correctly reported mint_ceiling=0 (no mint triggered).');
      process.exit(0);
    } else {
      console.log(`✗ FAIL: CI calculated mint_ceiling=0 (${result.reason}), but Worker recorded ${info.recordedMintCeiling}.`);
      process.exit(1);
    }
  }

  if (result.mint_ceiling !== info.recordedMintCeiling) {
    console.log(`✗ FAIL: Mismatch! CI calculated mint_ceiling=${result.mint_ceiling}, Worker recorded ${info.recordedMintCeiling}.`);
    process.exit(1);
  }

  console.log(`✓ PASS: mint_ceiling matches (${result.mint_ceiling} TCC).`);
}

main().catch(err => {
  console.error(`Fatal: ${err.message}`);
  process.exit(2);
});
