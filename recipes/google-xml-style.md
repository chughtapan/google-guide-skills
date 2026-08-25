# Google XML Document Format Style

## Scope and precedence

Use this guide when designing a new machine-consumed XML format or reviewing its schema and
contract. Do not apply it to rich-text formats, generated XML, or a request to reformat an
existing document. Reuse an established format when practical. When extending one, its
conventions take precedence. Treat this 2008 guide as design guidance; current standards,
interoperability requirements, and project rules win.

## Workflow

1. Identify the producers, consumers, compatibility lifetime, validation needs, and likely
   extensions.
2. Check whether an existing extensible format can represent the data without repurposing its
   fields.
3. Define the schema and normative behavior together. Specify defaults, whitespace, ordering,
   unknown content, and invalid input.
4. Test representative documents with standard parsers and validators in each supported
   environment.
5. Review the design for consistency, extensibility, and local reasoning before publishing it.

## Format rules

### Schema and namespaces

- Provide a machine-checkable schema. Use the schema language required by the ecosystem; the
  source guide's RELAX NG preference is not a reason to reject an established modern toolchain.
- Put new element names in a namespace and normally use it as the default namespace. Leave
  attributes unqualified unless they come from, or are intended for, another vocabulary.
- Use a stable HTTP(S) namespace URI. Do not change it unless element or attribute semantics
  become incompatibly different.
- Keep prefixes short, lowercase, and stable. Do not use single-letter prefixes.

### Names and values

- Use `lowerCamelCase` ASCII names for elements, attributes, and enumerated values. Prefer clear
  names over abbreviations; treat acronyms as words.
- Use base-10 signed integers or IEEE doubles unless the domain requires another numeric model.
- Prefer extensible enumerations to booleans. If a boolean is required, accept and emit only
  `true` or `false` unless compatibility dictates otherwise.
- Represent timestamps with RFC 3339 and prefer UTC when local time is not part of the meaning.
- Avoid embedding a second ad hoc syntax in text or attributes. State whitespace normalization
  rules explicitly.

### Elements and attributes

- Do not use mixed content for machine data. Do not add wrapper elements whose only purpose is to
  contain repeated children.
- Never depend on attribute order. Keep attribute sets small; move related or extensible data
  into child elements.
- Use elements for repeated, ordered, structured, large, multiline, streamable, or
  natural-language data.
- Use attributes for identifiers, references, controlled codes, processing metadata, and values
  inherited by descendants.
- Do not encode ordered series as `item1`, `item2`, and so on. Do not place line-sensitive values
  in attributes.

### Encoding and extensibility

- Use UTF-8. Parse with a standard XML parser; never depend on indentation, quote choice, CDATA,
  empty-tag spelling, or attribute order.
- Base64-encode embedded binary data, and link to it instead when it is large.
- Avoid new processing instructions. Do not carry application data in comments.
- Define how readers handle unknown elements, attributes, and enumeration values so compatible
  extensions can be added later.
- Keep namespace mappings consistent and use two-space indentation only as a human-readable
  serialization convention, never as part of the contract.

## Review output

Lead with `Ready` or `Needs changes`. For each material issue, report:

- `Contract area`: schema, namespace, name, value, structure, encoding, or compatibility.
- `Evidence`: the schema rule, example document, or implementation behavior.
- `Impact`: ambiguity, invalid data, interoperability failure, or migration cost.
- `Fix`: the smallest concrete format or specification change, plus a compatibility plan when
  existing consumers are affected.

Run the project validator and compatibility tests after any change. State untested consumers and
remaining migration risk.
