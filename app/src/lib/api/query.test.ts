import assert from "node:assert/strict";
import { test } from "node:test";
import { isResourceId, parsePaginationQuery } from "./query.ts";

const parse = (query: string) =>
	parsePaginationQuery(new URL(`http://localhost/x${query}`));

test("pagination defaults to page 1 with 20 items", () => {
	assert.deepEqual(parse(""), { page: 1, page_size: 20 });
});

test("pagination accepts decimal integers inside the documented range", () => {
	assert.deepEqual(parse("?page=3&page_size=100"), { page: 3, page_size: 100 });
});

test("pagination rejects malformed, repeated, unknown and out-of-range input", () => {
	for (const query of [
		"?page=1.5",
		"?page=-1",
		"?page=",
		"?page=0",
		"?page_size=101",
		"?page=1&page=2",
		"?view=ui",
		"?page=1e3",
	]) {
		assert.equal(parse(query), null, query);
	}
});

test("resource ids are opaque tokens, never paths", () => {
	assert.equal(isResourceId("3f2a9c1e"), true);
	assert.equal(isResourceId("evt_001"), true);
	assert.equal(isResourceId("../etc"), false);
	assert.equal(isResourceId(""), false);
});
