# notes
- I'm building an receipts scanner with OCR and AI to help user track their spending and get insights.
- Ask clarification questions if you don't fully understand the goal or what to building. DONOT make assumptions.
- this is an MVP app, don't over-engineer, keep it simple. the core value is to provide a simple and intuitive way to scan receipts and get insights.
- if possible, first make it runnable locally and use docker to containerize the app.
- deployment should be simple and idempotent. there must a clear way to know all the resources and configurations, everything should be tracked. there should be a way to tear down everything easily.
- deployment process should also include update, rollback, and delete.
- instruction to run the app should be simple and clear. it should include all the steps to run the app locally and in the cloud.
- if the web app layout could be optimized for mobile, it would be great. so we can delay building the mobile app. but we should keep in mind that we may need to build a mobile app in the future. so we should design the backend in a way that it can be easily consumed by a mobile app.
- please see the ./stitch_receipt_scanner/ and ./stitch_receipt_scanner/lumina_ledger/DESIGN.md for the UI theme, design system, mobile app, desktop website example.
