import readline from "node:readline";
import npa from "npm-package-arg";

const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });

for await (const line of input) {
  if (!line.trim()) continue;
  try {
    const request = JSON.parse(line);
    if (typeof request.spec !== "string") throw new TypeError("spec must be a string");
    const parsed = npa(request.spec);
    process.stdout.write(`${JSON.stringify({
      name: parsed.name ?? null,
      rawSpec: parsed.rawSpec,
      type: parsed.type,
      fetchSpec: parsed.fetchSpec,
    })}\n`);
  } catch (error) {
    process.stdout.write(`${JSON.stringify({ error: String(error) })}\n`);
  }
}
