# Security

- Never commit `.env`, API keys, customer images, internal paths, or Cognex/customer source code.
- Repository samples are AI-generated virtual accident images, not real people, vehicles,
  accident scenes, or customer data. Use only generated or explicitly public test images.
- The application keeps a session API key in process memory only; it is not written to SQLite.
- Before publishing a release ZIP, remove runtime DB files, logs, and personal test images.
