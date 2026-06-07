import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { MarkdownContent } from "../components/MarkdownContent";

test("renders GFM tables and highlighted fenced code", () => {
  const html = renderToStaticMarkup(
    <MarkdownContent>
      {"| File | Score |\n| --- | ---: |\n| app.py | 100 |\n\n```python\nif ready:\n    run()\n```"}
    </MarkdownContent>
  );

  assert.match(html, /<table>/);
  assert.match(html, /<td>app\.py<\/td>/);
  assert.match(html, /class="hljs language-python"/);
  assert.match(html, /class="hljs-keyword"/);
});
