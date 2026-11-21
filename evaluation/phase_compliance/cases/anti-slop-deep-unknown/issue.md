**Version:** `oxlint-plugin-anti-slop` 0.1.2, upstream `main` at `13909c9`. Read from source with oxlint 1.90.0 as the target; I did not run a RuleTester case.

**Gap.** No rule reports `unknown` when it sits inside an array type or an object type's field. The checks that look for `unknown` only look at the top of a type (or a union member, or `Promise<unknown>`), so a boundary type can still carry untyped data into the code.

**Repro, with all of the rules below on as errors:** `no-unknown-parameters`, `no-unknown-returns`, `no-unknown-type-aliases`, `no-unsafe-dictionary-type`, `no-known-value-widening`, `no-object-parameters`.

```ts
// 1. unknown inside an array
export const a = (xs: unknown[]) => xs.length;       // also ReadonlyArray<unknown>, and as a return type
// 2. unknown as an object field
export const b = (o: { x: unknown }) => o.x;         // also as a return type
// 3. same two, through an alias
export type T = unknown[] | { x: unknown };
```

I expect no rule to fire on any of these lines. The reason, from the source:

- `containsUnknownType` in `src/shared/function-parameters.ts` matches `unknown`, a parenthesized type and a union, and stops there. It does not look inside `TSArrayType` or a `TSTypeLiteral` member.
- `no-unknown-returns` resolves only `unknown`, a union and `Promise<unknown>`/`PromiseLike<unknown>`.
- `no-unsafe-dictionary-type` is about open dictionaries (`Record<string, unknown>`, index signatures). A named field `x: unknown` is not one.

**Expected.** A way to report an `unknown` anywhere inside a parameter or return type: array element, tuple element, object-type field, generic argument. A full rule is not needed. An option on `no-unknown-parameters` and `no-unknown-returns` (for example `deep: true`) would do. Keeping today's allowances (a type guard's subject, `cause`) would still make sense.

**Closest existing rules:**

- `no-unknown-parameters` and `no-unknown-returns`: same intent, shallow match only.
- `no-unknown-type-aliases`: same, for aliases of bare `unknown`.
- `no-unsafe-dictionary-type`: catches `Record<string, unknown>`, but not a named-field object or an array.
- `no-known-value-widening`: different direction (a known value passed into a broad type).

I searched open and closed issues for "unknown", "array" and "unknown[]" and found no report of this. #29 and #30 (unions that contain `unknown`) are the nearest, and they are closed.

