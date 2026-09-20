# LEXA Web Experience

This package contains the customer-facing LEXA web experience.

## Current experience

- LEXA branded public home page
- Sign in and workspace creation
- Multiple workspace selection
- Responsive business workspace shell
- Products workspace with live tenant data
- Existing inventory workspace source retained for the next product phase
- Customer-friendly service and authentication messaging

The public experience does not display internal service diagnostics, request identifiers, database details or release tooling information.


## Rapid development mode

During active product development the web app can open the workspace directly. Set `NEXT_PUBLIC_LEXA_OPEN_MODE=true` for the development build. The API must have its guarded development session enabled.

This mode does not remove database isolation or permissions; it only removes the browser authentication interruption.
