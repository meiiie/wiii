# Wiii licensing

Wiii's original core material is licensed under the MIT License in `LICENSE`.
The Apache-2.0 SDK boundary and third-party licenses remain separate.

## Ownership record

On 2026-08-16, the project owner confirmed that **Meiiie** owns and controls
the rights needed to license Wiii. **The Wiii Lab** is the project and brand
identity operated by Meiiie. This record does not replace or remove
third-party licenses, contributor attribution, or rights that remain with
their respective owners.

## License map

| Scope | Public license |
| --- | --- |
| Original project material outside `sdk/`, unless a file says otherwise | MIT License (`MIT`) |
| Material inside `sdk/` with an Apache SPDX header or covered by `sdk/LICENSE` | Apache License 2.0 (`Apache-2.0`) |
| Third-party, vendored, generated, research-reference, or externally sourced material | Its own license and notices |

`wiii-desktop/src/neko-chill/completion-sound.ts` is adapted from Neko Core
and retains its `AGPL-3.0-only` license and attribution. The full license text
is shipped in [`LICENSES/AGPL-3.0-only.txt`](LICENSES/AGPL-3.0-only.txt).
The MIT license for original Wiii material does not relicense this adaptation
or the separately bundled Neko Core runtime.

The `sdk/` path is a hard licensing boundary. The FastAPI service, WiiiRunner,
desktop application, and their internal clients are part of the MIT-licensed
product unless a file carries an explicit different license. There is no
separately published Apache SDK yet.

Future Apache SDK code must be independently usable as a client/protocol
library, must not import Wiii implementation modules, must carry
`SPDX-License-Identifier: Apache-2.0`, and must ship its own `LICENSE` and
`NOTICE` files.

## Use and redistribution

MIT permits commercial use, modification, distribution, and sublicensing
subject to its copyright and permission notice requirements. No separate
commercial license is required for uses permitted by MIT or Apache-2.0.
See [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md).

Earlier valid license grants remain valid. A copy of the MIT text is retained in
[`LICENSES/MIT.txt`](LICENSES/MIT.txt).

## Contributions and trademarks

Contributions to the MIT-licensed core must follow
[CONTRIBUTOR-LICENSE-POLICY.md](CONTRIBUTOR-LICENSE-POLICY.md). Code licenses
do not grant rights to the Wiii or The Wiii Lab names, logos, or branding; see
[TRADEMARKS.md](TRADEMARKS.md).
