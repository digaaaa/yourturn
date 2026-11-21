const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { test } = require("node:test");
const { runInNewContext } = require("node:vm");

const source = readFileSync("ui/api.js", "utf8");
const timeout = () => Object.assign(new Error("signal timed out"), { name: "TimeoutError" });

function setup(results) {
  const calls = [];
  const delays = [];
  const api = runInNewContext(source + "\napi;", {
    AbortSignal: { timeout: (milliseconds) => milliseconds },
    TypeError,
    fetch: async (url, options) => {
      calls.push({ url, options });
      const result = results.shift();
      if (result instanceof Error) throw result;
      return result;
    },
    setTimeout: (resolve, delay) => { delays.push(delay); resolve(); },
  });
  return { api, calls, delays };
}

test("a cold read retries a timeout and transient HTTP response, then loads data", async () => {
  const data = [{ id: 1 }];
  const { api, calls, delays } = setup([timeout(), { status: 503 }, {
    status: 200, ok: true, json: async () => data,
  }]);
  let retries = 0;
  assert.equal(await api("https://example.invalid", "/chores/", { onRetry: () => retries++ }), data);
  assert.equal(retries, 2);
  assert.deepEqual(delays, [1000, 2000]);
  assert.ok(calls.every(({ options }) => options.signal === 35_000));
});

test("a persistently unavailable read gives a friendly error after three attempts", async () => {
  const { api, calls } = setup([{ status: 502 }, { status: 503 }, { status: 504 }]);
  await assert.rejects(api("https://example.invalid", "/supplies/"), /still starting or unavailable/);
  assert.equal(calls.length, 3);
});

test("a write timeout is never retried", async () => {
  const { api, calls } = setup([timeout()]);
  await assert.rejects(api("https://example.invalid", "/chores/1/done", { method: "POST" }), /check before submitting/);
  assert.equal(calls.length, 1);
});

test("a write keeps a server validation or unavailability message without retrying", async () => {
  const { api, calls } = setup([{
    status: 503, ok: false, json: async () => ({ error: "Roommate information is temporarily unavailable." }),
  }]);
  await assert.rejects(api("https://example.invalid", "/supplies/1/bought", { method: "POST" }), /Roommate information/);
  assert.equal(calls.length, 1);
});
