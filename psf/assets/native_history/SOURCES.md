# Original country-history snapshot

These 364 country-history definitions are from the user-supplied vanilla
Hearts of Iron IV script archive. Their original paths are `history/countries/`.
The supplied archive contains no reliable game-build version marker. This
snapshot is not a claim of compatibility with every HOI4 version or overhaul.

The strict vanilla adapter preserves each original filename and every original
statement, and inserts PSF bootstrap calls at root/date boundaries. A compile
with `--vanilla /path/to/game` uses that installation's original history instead.
The build report records a SHA-256 for every input and a combined snapshot hash.
The supplied NOR source is missing its final dated-block closing brace; only
that exact known input hash receives a documented closing-brace output repair.
Its empty pre-Man-the-Guns conditional is preserved as comments in the output.
Its bundled source bytes are retained unchanged.
Compat mode does not override country history. Never supply an already-generated
PSF mod directory as the original source.

These game definitions remain Paradox Interactive material, not MIT-licensed
PSF work. See the repository THIRD_PARTY_NOTICES.md. A licensed game is required.
