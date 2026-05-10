"""
AI collaboration handler mixin.
"""

import json
from core import ok, error


class AIHandlers:
    """ai;status / ai;messages"""

    def _handle_ai_status(self, params: list) -> dict:
        mode = (params[0].upper() if params else 'A') if params and params[0] else 'A'
        if mode not in ('A', 'B'):
            mode = 'A'

        s = self._ai_status
        if not s:
            return ok('No status reported yet. Ask your AI collaborator to POST /ai_status.',
                      status='unknown')

        ctx = s.get('context_pct', 0)
        comp = s.get('compactions', 0)

        if ctx >= 80 or comp >= 3:
            health = 'critical'
        elif ctx >= 60 or comp >= 1:
            health = 'warning'
        else:
            health = 'healthy'

        if mode == 'A':
            text = f"Tide \U0001f30a  {ctx}% ctx  {comp} compactions  {health}"
            return ok(text,
                      model=s.get('model', ''),
                      context_pct=ctx,
                      compactions=comp,
                      health=health)

        # Mode B
        text = (
            f"Tide \U0001f30a  Collaborator Status\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"Model:       {s.get('model', '?')}\n"
            f"Context:     {s.get('context_used','?')} / {s.get('context_max','?')} ({ctx}%)\n"
            f"Compactions: {comp}\n"
            f"Tokens:      {s.get('tokens_in','?')} in / {s.get('tokens_out','?')} out\n"
            f"Cache:       {s.get('cache_hit','?')} hit, {s.get('cache_cached','?')} cached\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"Health:      {health}"
        )
        return ok(text,
                  model=s.get('model', ''),
                  context_pct=ctx,
                  compactions=comp,
                  tokens_in=s.get('tokens_in', ''),
                  tokens_out=s.get('tokens_out', ''),
                  cache_hit=s.get('cache_hit', ''),
                  health=health)

    def _handle_ai_messages(self, params: list) -> dict:
        mode = params[0] if params else ''
        msg_file = self.cache_dir / 'messages.json'

        # ── Write mode ──
        if mode == 'push':
            if len(params) < 2:
                return error('missing_param', 'Missing parameter: msg_json')
            # JSON with commas gets split by directive parser, rejoin
            json_str = ','.join(params[1:]) if len(params) > 2 else params[1]
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                return error('bad_request', 'msg_json format invalid')
            msg_file.parent.mkdir(parents=True, exist_ok=True)
            msg_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            count = len(data.get('messages', []))
            return ok(f'Messages pushed, {count} total')

        # ── Read mode ──
        n = int(mode) if mode else 1
        if not msg_file.exists():
            return error('no_messages', 'No messages yet. Write via ai;messages,push first')
        data = json.loads(msg_file.read_text(encoding='utf-8'))
        messages = data.get('messages', [])
        if not messages:
            return ok('(empty)')
        if n > len(messages):
            n = len(messages)
        recent = messages[-n:] if n > 0 else messages

        lines = []
        for i, msg in enumerate(recent):
            role = msg.get('role', '?')
            content = msg.get('content', '')
            idx = len(messages) - len(recent) + i + 1
            lines.append(f"--- {role} (#{idx}) ---\n{content}")
        return ok('\n\n'.join(lines))
