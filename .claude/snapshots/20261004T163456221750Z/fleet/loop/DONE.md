# Done ledger

Append-only. git-manager writes one line per ticket outcome. Everyone reads the tail first.
Format: `<date> | <ticket-id> | <owner> | <landed <sha> / reverted <sha> / stuck / failed> | <files, comma-separated> | <one-line what changed>`

