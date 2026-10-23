import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const root = new URL('../', import.meta.url);
const read = (path) => readFileSync(new URL(path, root), 'utf8');

test('internal team chat is connected to real tenant/branch-scoped API calls', () => {
  const page = read('app/team-chat/page.tsx');
  const api = read('lib/api.ts');
  const shell = read('components/app-shell.tsx');
  const navigation = read('lib/navigation.mjs');
  assert.match(page, /getTeamConversations/);
  assert.match(page, /getTeamMessages/);
  assert.match(page, /sendTeamMessage/);
  assert.match(page, /markTeamConversationRead/);
  assert.match(page, /Updates every 12 seconds/);
  assert.match(page, /Branch conversations are visible only to team members assigned to that branch/);
  assert.match(api, /postIdempotent<TeamMessage>/);
  assert.match(navigation, /\["\/team-chat", "Team chat", "chat"\]/);
});

test('chat has responsive layout, bounded messages and no AI/external provider claim', () => {
  const page = read('app/team-chat/page.tsx');
  const css = read('app/globals.css');
  assert.match(page, /maxLength=\{4000\}/);
  assert.match(page, /not customer-facing WhatsApp or SMS/);
  assert.match(css, /\.team-chat-layout\{display:grid/);
  assert.match(css, /@media\(max-width:800px\)\{\.team-chat-heading/);
});
