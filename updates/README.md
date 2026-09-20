# Update Manifests

This directory stores the public release manifest for SmartClipboard.

- `latest.json` is signed by the release workflow via Ed25519 digital signature.
- `latest-native.json` is the same signed format for the Rust + Tauri native build, published by the `release-native` job.
- Do not edit these files manually; they are generated and signed during the GitHub Actions release process.
