# Incoming LEXA Packages

Put future implementation ZIPs in this directory. The GitHub workflow extracts them into the repository root.

For explicit obsolete-file removal, include either `DELETE.txt` or `.lexa-delete` in the ZIP. Use one repository-relative path per line. Lines beginning with `#` are ignored.

Example:

```text
old/path/to/remove.ts
old/docs/obsolete.md
```
