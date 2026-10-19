package opendpo.triage_test

import data.opendpo.triage

sample := [
	{
		"id": "R-ALL", "pack": "p", "pack_version": "0.1.0", "kind": "trigger", "result": {"assessment": "x"},
		"when": {"all": [
			{"fact": "ccpa.applies", "equals": true},
			{"any": [
				{"fact": "sells_or_shares", "equals": true},
				{"fact": "data_categories", "contains": "sensitive"},
			]},
		]},
	},
	{
		"id": "R-NOT", "pack": "p", "pack_version": "0.1.0", "kind": "trigger", "result": {"obligation": "y"},
		"when": {"all": [
			{"fact": "ai.used", "equals": true},
			{"not": {"fact": "decision_domain", "in": ["advertising"]}},
		]},
	},
	{
		"id": "R-NUM", "pack": "p", "pack_version": "0.1.0", "kind": "applicability", "result": {"law": "z"},
		"when": {"fact": "consumers_ca", "at_least": 100000},
	},
]

test_nested_any_matches if {
	"R-ALL" in triage.matched with data.opendpo.content.rules as sample
		with input as {"facts": {"ccpa.applies": true, "sells_or_shares": false, "data_categories": ["sensitive"]}}
}

test_all_fails_when_one_part_fails if {
	not "R-ALL" in triage.matched with data.opendpo.content.rules as sample
		with input as {"facts": {"ccpa.applies": false, "sells_or_shares": true}}
}

test_not_excludes_advertising if {
	not "R-NOT" in triage.matched with data.opendpo.content.rules as sample
		with input as {"facts": {"ai.used": true, "decision_domain": "advertising"}}
	"R-NOT" in triage.matched with data.opendpo.content.rules as sample
		with input as {"facts": {"ai.used": true, "decision_domain": "employment"}}
}

test_threshold if {
	"R-NUM" in triage.matched with data.opendpo.content.rules as sample
		with input as {"facts": {"consumers_ca": 100000}}
	not "R-NUM" in triage.matched with data.opendpo.content.rules as sample
		with input as {"facts": {"consumers_ca": 99999}}
}

test_missing_fact_never_matches if {
	not "R-NUM" in triage.matched with data.opendpo.content.rules as sample with input as {"facts": {}}
}

test_missing_facts_reported if {
	"consumers_ca" in triage.missing_facts with data.opendpo.content.rules as sample
		with input as {"facts": {"ccpa.applies": true}}
}

test_no_rules_loaded_means_no_results if {
	count(triage.matched) == 0 with input as {"facts": {"ccpa.applies": true}}
}
