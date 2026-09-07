import assert from "node:assert/strict";
import test from "node:test";
import npa from "npm-package-arg";

test("npm-package-arg classifies registry, alias, git, URL, and directory specs", () => {
  assert.equal(npa("@scope/name@^2").type, "range");
  assert.equal(npa("alias@npm:real@1").type, "alias");
  assert.equal(npa("git+https://github.com/org/repo.git").type, "git");
  assert.equal(npa("https://example.invalid/package.tgz").type, "remote");
  assert.equal(npa("./local").type, "directory");
});
