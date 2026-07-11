# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: 17-investigation.spec.ts >> investigation — modal frame ampliado
- Location: src/test/e2e/visual-audit/17-investigation.spec.ts:217:1

# Error details

```
Error: Channel closed
```

```
Error: locator.waitFor: Target page, context or browser has been closed
Call log:
  - waiting for getByText('92% confiança') to be visible

```

```
Error: browserContext.close: Target page, context or browser has been closed
```