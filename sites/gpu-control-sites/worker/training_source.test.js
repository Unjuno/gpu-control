import assert from "node:assert/strict";
import test from "node:test";

import { resolvePublicDefaultBranchCommit, verifyGithubCommit } from "./training_source.js";

test("resolves only a public repository default branch to a pinned immutable commit", async () => {
  const urls = [];
  const fetchImpl = async (url, options) => {
    urls.push({ url: String(url), options });
    if (urls.length === 1) return new Response(JSON.stringify({
      private: false, archived: false, default_branch: "experiment/main",
    }), { status: 200, headers: { "content-type": "application/json" } });
    return new Response(JSON.stringify([{ sha: "f".repeat(40) }]), {
      status: 200, headers: { "content-type": "application/json" },
    });
  };
  const source = await resolvePublicDefaultBranchCommit("Owner/Project", fetchImpl);
  assert.deepEqual(source, { repository: "owner/project", commit: "f".repeat(40),
    default_branch: "experiment/main", visibility: "public" });
  assert.equal(urls.length, 2);
  assert.equal(urls[0].url, "https://api.github.com/repos/owner/project");
  const commitUrl = new URL(urls[1].url);
  assert.equal(commitUrl.origin, "https://api.github.com");
  assert.equal(commitUrl.pathname, "/repos/owner/project/commits");
  assert.equal(commitUrl.searchParams.get("sha"), "experiment/main");
  assert.equal(commitUrl.searchParams.get("per_page"), "1");
  for (const { options } of urls) {
    assert.equal(options.method, "GET");
    assert.equal(options.redirect, "error");
    assert.equal(options.headers["x-github-api-version"], "2022-11-28");
  }
});

test("verifies an explicitly selected custom commit with the exact-repository GitHub token", async () => {
  const token = "installation-token-never-return-this";
  let requested;
  const result = await verifyGithubCommit("Owner/Project", "a".repeat(40), async (url, options) => {
    requested = { url: String(url), options };
    return new Response(JSON.stringify({ sha: "a".repeat(40) }), { status: 200 });
  }, token);
  assert.equal(result.repository, "owner/project");
  assert.equal(result.commit, "a".repeat(40));
  assert.equal(requested.url, `https://api.github.com/repos/owner/project/git/commits/${"a".repeat(40)}`);
  assert.equal(requested.options.headers.authorization, `Bearer ${token}`);
  assert.equal(JSON.stringify(result).includes(token), false);
  await assert.rejects(verifyGithubCommit("owner/project", "b".repeat(40), async () =>
    new Response(JSON.stringify({ sha: "c".repeat(40) }), { status: 200 })),
  { message: "TRAINING_GITHUB_COMMIT_UNAVAILABLE" });
});

test("fails closed for private, archived, and malformed GitHub source metadata", async () => {
  await assert.rejects(resolvePublicDefaultBranchCommit("owner/project", async () =>
    new Response(JSON.stringify({ private: true }), { status: 200 })),
  { message: "TRAINING_GITHUB_PRIVATE_REQUIRES_APP" });
  await assert.rejects(resolvePublicDefaultBranchCommit("owner/project", async () =>
    new Response(JSON.stringify({ private: false, archived: true, default_branch: "main" }), { status: 200 })),
  { message: "TRAINING_GITHUB_REPOSITORY_ARCHIVED" });
  await assert.rejects(resolvePublicDefaultBranchCommit("owner/project", async () =>
    new Response(JSON.stringify({ private: false, archived: false, default_branch: "../../evil" }), { status: 200 })),
  { message: "TRAINING_GITHUB_RESPONSE_INVALID" });
  await assert.rejects(resolvePublicDefaultBranchCommit("owner/project", async () =>
    new Response("not found", { status: 404 })),
  { message: "TRAINING_GITHUB_REPOSITORY_NOT_PUBLIC" });
});

