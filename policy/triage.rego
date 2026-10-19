# OpenDPO triage evaluator (WF-05, design principle 9: rules decide).
#
# Reads the verified rules the API loads into data.opendpo.content.rules and
# the structured facts in input.facts, and returns which rules match. The
# same facts always give the same result; no model is involved. Unverified
# rules are never loaded here (CNT-01).
#
# A condition is a fact test, or all / any / not over conditions, at most
# three levels deep. Rego has no recursion, so each level is written out.
package opendpo.triage

default rules := []

rules := data.opendpo.content.rules

has(c, k) if k in object.keys(c)

# Level 1: a test on one fact. A missing fact never matches.
leaf(c) if {
	has(c, "equals")
	input.facts[c.fact] == c.equals
}

leaf(c) if {
	has(c, "in")
	input.facts[c.fact] in c["in"]
}

leaf(c) if {
	has(c, "contains")
	c["contains"] in input.facts[c.fact]
}

leaf(c) if {
	has(c, "at_least")
	input.facts[c.fact] >= c.at_least
}

# Level 2
l2(c) if leaf(c)

l2(c) if {
	has(c, "all")
	every x in c.all { leaf(x) }
}

l2(c) if {
	has(c, "any")
	some x in c.any
	leaf(x)
}

l2(c) if {
	has(c, "not")
	not leaf(c["not"])
}

# Level 3
l3(c) if l2(c)

l3(c) if {
	has(c, "all")
	every x in c.all { l2(x) }
}

l3(c) if {
	has(c, "any")
	some x in c.any
	l2(x)
}

l3(c) if {
	has(c, "not")
	not l2(c["not"])
}

matched contains r.id if {
	some r in rules
	l3(r.when)
}

results := [{"rule": r.id, "pack": r.pack, "pack_version": r.pack_version, "kind": r.kind, "result": r.result} |
	some r in rules
	r.id in matched
]

# Facts a rule refers to that the caller did not supply: triage is not
# complete until these are answered or routed to an analyst (WF-08).

missing_facts contains f if {
	some r in rules
	walk(r.when, [path, value])
	path[count(path) - 1] == "fact"
	f := value
	not has(input.facts, f)
}
