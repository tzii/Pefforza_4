import assert from 'node:assert/strict';
import test from 'node:test';
import { DropTimeline } from '../scripts/preview_gui.mjs';

const drop = {id:100, row:5, column:3, player:1, duration:270, elapsed:20};

test('motion advances between network snapshots at any display refresh rate', () => {
  const clock = new DropTimeline();
  clock.sync(drop, 1000, 5);
  assert.equal(clock.progress(1000), 25/270);
  assert.ok(clock.progress(1008) > clock.progress(1000));
  assert.ok(clock.progress(1016) > clock.progress(1008));
  assert.equal(clock.progress(1245), 1);
});

test('duplicate snapshots do not restart or rewind an ongoing drop', () => {
  const clock = new DropTimeline();
  clock.sync(drop, 1000);
  const before = clock.progress(1050);
  clock.sync({...drop, elapsed:25}, 1050, 15);
  assert.equal(clock.progress(1050), before);
});

test('cancel, retry, and reduced motion preserve the authoritative position', () => {
  const clock = new DropTimeline();
  clock.sync(drop, 1000);
  assert.equal(clock.progress(1000, true), 1);
  clock.sync(null, 1005);
  assert.equal(clock.progress(1010), null);
  clock.sync({...drop, id:300, elapsed:0}, 1200);
  assert.equal(clock.progress(1200), 0);
  assert.equal(clock.progress(1100), 0);
  assert.equal(clock.progress(2000), 1);
});
