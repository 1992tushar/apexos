"""The Founder Command Center (Part 9) — a read-only projection, and nothing else.

This module owns **no entity, no table and no arithmetic** (R12.10, G15/G16). It asks
the parts that own each number for it and arranges the answers into the three questions
R12.1 puts in order: what happened · what needs attention · what should I do now.

That constraint is the whole design. Part 8 spent three checkpoints deleting places
where two screens disagreed about money, and a homepage is the single most tempting
place to add a fourth — a tile is one `select()` away, and nobody notices for months
that it subtracts credit notes when the receivable does not. So the rule here is
absolute: if a figure this page wants is not already exposed by the part that owns it,
it gets added **there** and read here.
"""
